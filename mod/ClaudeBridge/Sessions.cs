// Sessions.cs -- load a savegame from inside the running process.
//
// WHY THIS EXISTS.  The game has no command-line argument that loads a savegame --
// the complete list is --set-modding-env-vars, --ignore-mods, --safe-mode,
// --disable-store-sdk, --custom-translations, --danger-bypass-modded-savegame-checks,
// --ignore-hw-checks and --no-dynamic-content.  So relaunching the exe only ever
// gets you a main menu, and an agent that can start the game but not open a world
// has gained nothing.  This closes that gap, and with it the last thing in the loop
// that needed a person.
//
// At the main menu the game is NOT idle: it renders a background world, so
// GameHelper.Core is non-null and a live IMapModel is reachable -- but it is the
// menu's own decorative save ("Menu Background Supporter"), not yours.  Anything
// that writes must check `status` first.  That one is a trap worth naming.
//
// The chain, assembled from the game's own declarations:
//
//   Game.Orchestration.GameBootstrapper.GameOrchestrator      static field
//     -- a STATIC class, therefore an abstract one, therefore invisible to any
//        UnityEngine.Object scan.  It is the only holder of the orchestrator.
//   new SavegameBlobReader(path, core.DataSerializers, logger)
//   new GameStartOptionsContinueExisting(reader, menuMode: false, uid, isFresh: false)
//   orchestrator.LoadSession(options)                         async, fire and forget

using System;
using System.IO;
using System.Linq;
using System.Reflection;
using ShapezShifter.Kit;

namespace ClaudeBridge
{
    internal static class Sessions
    {
        private const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
                                       | BindingFlags.Instance | BindingFlags.Static;

        internal static string PersistentDir()
        {
            var dll = Assembly.GetExecutingAssembly().Location;
            return Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(dll)));
        }

        internal static string List()
        {
            var dir = Path.Combine(PersistentDir(), "savegames");
            if (!Directory.Exists(dir)) return "no savegames folder at " + dir;
            var sb = new System.Text.StringBuilder();
            foreach (var d in Directory.GetDirectories(dir))
            {
                var newest = Newest(d);
                sb.Append(Path.GetFileName(d));
                sb.Append(newest == null ? "   (empty)"
                        : "   " + Path.GetFileName(newest) + "   "
                          + new FileInfo(newest).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"));
                sb.Append('\n');
            }
            return sb.ToString().TrimEnd();
        }

        private static string Newest(string dir)
        {
            var files = Directory.GetFiles(dir, "*.spz2");
            if (files.Length == 0) return null;
            return files.OrderByDescending(f => new FileInfo(f).LastWriteTime).First();
        }

        /// <summary>Load the newest snapshot of a savegame by its folder uid.</summary>
        internal static string Load(string uid)
        {
            if (string.IsNullOrEmpty(uid)) return "ERROR load <savegame-uid>\n" + List();

            var dir = Path.Combine(Path.Combine(PersistentDir(), "savegames"), uid);
            if (!Directory.Exists(dir)) return "ERROR no savegame folder '" + uid + "'\n" + List();
            var file = Newest(dir);
            if (file == null) return "ERROR no .spz2 in " + dir;

            var bootT = Reflect.FindType("Game.Orchestration.GameBootstrapper");
            if (bootT == null) return "ERROR GameBootstrapper not found";
            var orchF = bootT.GetField("GameOrchestrator", Any);
            if (orchF == null) return "ERROR GameBootstrapper has no GameOrchestrator field";
            var orch = orchF.GetValue(null);
            if (orch == null) return "ERROR GameOrchestrator is null";

            var core = GameHelper.Core;
            if (core == null) return "ERROR GameHelper.Core is null -- cannot get DataSerializers";
            var serializers = core.DataSerializers;

            // Constructing a SavegameBlobReader directly is NOT enough: the constructor
            // only records the source, leaving Blobs / Metadata / StringLUT empty, and
            // Init_3_1_ExistingSavegame then dies on a NullReferenceException before it
            // has logged anything useful.  SaveFileAccessor.Read is the factory that
            // actually opens the archive and fills those in.
            var accT = Reflect.FindType("SaveFileAccessor");
            if (accT == null) return "ERROR SaveFileAccessor not found";
            var accCtor = accT.GetConstructors(Any).FirstOrDefault(c => c.GetParameters().Length == 1);
            if (accCtor == null) return "ERROR SaveFileAccessor has no 1-arg constructor";
            object reader;
            try
            {
                var accessor = accCtor.Invoke(new object[] { FindLogger() });
                var read = accT.GetMethod("Read", Any);
                if (read == null) return "ERROR no SaveFileAccessor.Read";
                reader = read.Invoke(accessor, new object[] { file, serializers });
            }
            catch (Exception e) { return "ERROR reading the savegame: " + Unwrap(e); }
            if (reader == null) return "ERROR SaveFileAccessor.Read returned null";

            var optT = Reflect.FindType("GameStartOptionsContinueExisting");
            if (optT == null) return "ERROR GameStartOptionsContinueExisting not found";
            var oc = optT.GetConstructors(Any).FirstOrDefault(c => c.GetParameters().Length == 4);
            if (oc == null) return "ERROR GameStartOptionsContinueExisting has no 4-arg constructor";
            var options = oc.Invoke(new object[] { reader, false, uid, false });

            var load = orch.GetType().GetMethod("LoadSession", Any);
            if (load == null) return "ERROR no LoadSession on " + orch.GetType().FullName;
            try { load.Invoke(orch, new[] { options }); }     // async: returns a Task we do not await
            catch (Exception e) { return "ERROR LoadSession threw: " + Unwrap(e); }

            return "loading " + Path.GetFileName(file) + " (uid " + uid + ") -- poll `status` until the "
                 + "island count matches; the load is asynchronous";
        }

        internal static string Quit()
        {
            var bootT = Reflect.FindType("Game.Orchestration.GameBootstrapper");
            var m = bootT?.GetMethod("Dispose", Any);
            if (m == null) return "ERROR no GameBootstrapper.Dispose";
            m.Invoke(null, null);
            return "shutting down";
        }

        /// <summary>Any live ILogger. SaveFileAccessor takes one, and passing null works
        /// only until something decides to log; borrowing a real one is cheaper than
        /// finding out which call that is. Falls back to null, which is still better
        /// than refusing to try.</summary>
        private static object FindLogger()
        {
            var iLogger = Reflect.FindType("Core.Logging.ILogger") ?? Reflect.FindType("ILogger");
            if (iLogger == null) return null;
            foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type[] ts;
                try { ts = a.GetTypes(); } catch { continue; }
                foreach (var t in ts)
                {
                    FieldInfo[] fs;
                    try { fs = t.GetFields(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic); }
                    catch { continue; }
                    foreach (var f in fs)
                    {
                        if (!iLogger.IsAssignableFrom(f.FieldType)) continue;
                        object v; try { v = f.GetValue(null); } catch { continue; }
                        if (v != null) return v;
                    }
                }
            }
            return null;
        }

        private static string Unwrap(Exception e)
        {
            while (e is TargetInvocationException && e.InnerException != null) e = e.InnerException;
            return e.GetType().Name + ": " + e.Message;
        }
    }
}
