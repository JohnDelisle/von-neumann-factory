// ClaudeBridge -- stage 1: a mailbox, so the agent drives the game itself.
//
// Stage 0 registered console commands, which meant a human had to type them and
// read the answer off the screen: the game logs console INPUT to Player.log but not
// its output.  That is the whole reason for this stage.  Requests are files, replies
// are files, and nobody has to be sitting at the keyboard.
//
//     <persistent>/claude-bridge/in/<id>.txt     written by the agent: one command
//     <persistent>/claude-bridge/out/<id>.txt    written here: the reply
//     <persistent>/claude-bridge/log.txt         every request, with timing
//
// THREADING.  There is no network thread and no file watcher thread: the poll
// happens inside Tick, which the game calls on its own thread, so every game object
// is touched from the only place it is safe to touch one.  A background thread
// calling into Unity is the classic way to make this crash, and the cost of not
// doing it is one directory listing every quarter second.
//
// The reach into the live world, found with `tools/spz2api -- refs` (no method in
// any assembly RETURNS an IMapModel, which is why it looked unreachable):
//
//     ShapezShifter.Kit.GameHelper.Core     static -> IGameSessionManagers
//       .EntityPlacementRunner              public -> IEntityPlacementRunner
//         private field "Map"                      -> IMapModel
//
// Reflection rather than a cast to Game.Interaction.EntityPlacementRunner, so a
// renamed field yields a readable diagnostic from `status` -- including the fields
// that ARE present -- instead of a TypeLoadException at mod load.

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using Game.Core.Modding;
using ShapezShifter.Flow;
using ShapezShifter.Hijack;
using ShapezShifter.Kit;

namespace ClaudeBridge
{
    public sealed class ClaudeBridgeMod : IMod
    {
        internal const string Version = "0.6.0";

        private ModConsoleCommandsCreator.ModConsoleRewirer _console;
        private Mailbox _mailbox;
        private RewirerHandle _tickHandle;

        public ClaudeBridgeMod()
        {
            // Nothing in here may throw. If the constructor of a mod fails the mod does
            // not load at all, and with John away from the keyboard that would cost the
            // whole session -- so every step degrades to a log line instead.
            try
            {
                _mailbox = new Mailbox(BridgeRoot());
                _mailbox.Note("ClaudeBridge " + Version + " loaded");
            }
            catch (Exception e) { Console.WriteLine("ClaudeBridge: mailbox failed: " + e); return; }

            try { _tickHandle = GameRewirers.AddRewirer<ITickRewirer>(_mailbox); }
            catch (Exception e) { _mailbox.Note("FATAL: could not register tick rewirer: " + e); }

            try
            {
                _console = ModConsoleCommandsCreator.AddModCommands(this);
                // AddCommand hands us the live IDebugConsole. Keeping it is what turns
                // the bridge into a front end for EVERY command the game already has,
                // instead of only the handful compiled in here.
                _console.AddCommand(c =>
                {
                    Api.Console = c;
                    c.Register("status", _ => _mailbox.Note(Api.Status()), false);
                    c.Register("where", _ => _mailbox.Note("mailbox: " + _mailbox.Root), false);
                });
            }
            catch (Exception e) { _mailbox.Note("console commands unavailable: " + e.Message); }
        }

        public void Dispose()
        {
            try { GameRewirers.RemoveRewirer(_tickHandle); } catch { }
            _console?.Dispose();
        }

        /// <summary>`<persistent>/claude-bridge`, derived from where this DLL sits
        /// (`<persistent>/mods/ClaudeBridge/`) rather than from an environment
        /// variable the game process may not have inherited.</summary>
        private static string BridgeRoot()
        {
            try
            {
                var dll = Assembly.GetExecutingAssembly().Location;
                if (!string.IsNullOrEmpty(dll))
                {
                    var persistent = Path.GetDirectoryName(Path.GetDirectoryName(Path.GetDirectoryName(dll)));
                    if (!string.IsNullOrEmpty(persistent))
                        return Path.Combine(persistent, "claude-bridge");
                }
            }
            catch { }
            var env = Environment.GetEnvironmentVariable("SPZ2_PERSISTENT");
            return Path.Combine(string.IsNullOrEmpty(env) ? "." : env, "claude-bridge");
        }
    }

    // ---------------------------------------------------------------- the mailbox
    internal sealed class Mailbox : ITickRewirer
    {
        internal readonly string Root;
        private readonly string _in, _out, _log;
        private float _accum;

        internal Mailbox(string root)
        {
            Root = root;
            _in = Path.Combine(root, "in");
            _out = Path.Combine(root, "out");
            _log = Path.Combine(root, "log.txt");
            Directory.CreateDirectory(_in);
            Directory.CreateDirectory(_out);
        }

        internal void Note(string text)
        {
            try { File.AppendAllText(_log, DateTime.Now.ToString("HH:mm:ss") + "  " + text + "\n"); }
            catch { }
        }

        public bool Equals(IRewirer other) => ReferenceEquals(this, other);

        public void Tick(float deltaTime)
        {
            // Poll ~4x/second. Everything below runs on the game thread by construction.
            _accum += deltaTime;
            if (_accum < 0.25f) return;
            _accum = 0f;
            string[] files;
            try { files = Directory.GetFiles(_in, "*.txt"); } catch { return; }
            if (files.Length == 0) return;
            Array.Sort(files);
            foreach (var f in files)
            {
                var id = Path.GetFileNameWithoutExtension(f);
                string body, reply;
                try { body = File.ReadAllText(f).Trim(); }
                catch { continue; }                       // still being written; next tick
                var started = DateTime.Now;
                try { reply = Api.Dispatch(body); }
                catch (Exception e) { reply = "ERROR " + e.GetType().Name + ": " + e.Message + "\n" + e.StackTrace; }
                try
                {
                    File.WriteAllText(Path.Combine(_out, id + ".txt"), reply);
                    File.Delete(f);
                }
                catch (Exception e) { Note("could not answer " + id + ": " + e.Message); }
                Note(id + "  " + body.Replace("\n", " ") + "   -> " + reply.Length + " bytes in "
                     + (DateTime.Now - started).TotalMilliseconds.ToString("F0", CultureInfo.InvariantCulture) + "ms");
            }
        }
    }

    // ------------------------------------------------------------------ the verbs
    internal static class Api
    {
        /// <summary>The game's own debug console, captured when Shifter registers our
        /// commands. With it the bridge fronts every command the game already has.</summary>
        internal static object Console;

        private const string Verbs =
            "ping status inspect members | commands console <cmd> | speed <x> pause resume | "
          + "get <path> set <path> <v> call <path.Method> [args] find <type> statics <type> | saves load <uid> quit";

        internal static string Dispatch(string request)
        {
            var parts = request.Split(new[] { ' ', '\n', '\r', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            var verb = parts.Length > 0 ? parts[0].ToLowerInvariant() : "";
            var rest = parts.Skip(1).ToArray();
            switch (verb)
            {
                case "ping": return "pong " + ClaudeBridgeMod.Version;
                case "status": return Status();
                case "inspect": return Inspect();
                case "members": return Members(rest.FirstOrDefault());
                case "help": return Verbs;

                // ---- the game's own console, which is ~100 commands we did not write
                case "commands": return Commands(rest.FirstOrDefault() ?? "");
                case "console": return RunConsole(string.Join(" ", rest));

                // ---- simulation control: iteration speed is iteration cost
                case "speed": return Reflect.Set("core.SimulationSpeed.Speed", rest.FirstOrDefault() ?? "1");
                case "pause": return Reflect.Set("core.SimulationSpeed.IsPaused", "true");
                case "resume": return Reflect.Set("core.SimulationSpeed.IsPaused", "false");

                // ---- the general escape hatch (see Reflect.cs)
                case "get": return Reflect.Get(rest.FirstOrDefault() ?? "");
                case "set": return rest.Length < 2 ? "ERROR set <path> <value>"
                                                   : Reflect.Set(rest[0], string.Join(" ", rest.Skip(1)));
                case "call": return rest.Length < 1 ? "ERROR call <path.Method> [args]"
                                                    : Reflect.Call(rest[0], rest.Skip(1).ToArray());
                case "find": return Reflect.Find(rest.FirstOrDefault());
                case "statics": return Reflect.Statics(rest.FirstOrDefault() ?? "");

                // ---- session control: the last thing in the loop that needed a person
                case "saves": return Sessions.List();
                case "load": return Sessions.Load(rest.FirstOrDefault());
                case "quit": return Sessions.Quit();
                case "type": return Members(rest.FirstOrDefault());

                default: return "ERROR unknown verb '" + verb + "'. known: " + Verbs;
            }
        }

        private static string Commands(string prefix)
        {
            if (Console == null) return "ERROR the debug console was never handed to us";
            var m = Console.GetType().GetMethod("GetAutoCompletions", new[] { typeof(string) });
            if (m == null) return "ERROR no GetAutoCompletions on " + Console.GetType().FullName;
            var list = m.Invoke(Console, new object[] { prefix }) as System.Collections.IEnumerable;
            if (list == null) return "(none)";
            var all = list.Cast<object>().Select(x => x?.ToString()).Where(x => x != null).OrderBy(x => x).ToList();
            return all.Count + " commands\n  " + string.Join("\n  ", all);
        }

        private static string RunConsole(string command)
        {
            if (string.IsNullOrEmpty(command)) return "ERROR console <command>";
            if (Console == null) return "ERROR the debug console was never handed to us";
            var m = Console.GetType().GetMethod("ParseAndExecute",
                        new[] { typeof(string), typeof(Action<string>) });
            if (m == null) return "ERROR no ParseAndExecute on " + Console.GetType().FullName;
            var sb = new List<string>();
            Action<string> sink = s => sb.Add(s);
            m.Invoke(Console, new object[] { command, sink });
            return sb.Count == 0 ? "(no output)" : string.Join("\n", sb);
        }

        /// <summary>The live map, or null with `why` naming exactly which step failed.</summary>
        internal static object GetMap(out string why)
        {
            why = null;
            var core = GameHelper.Core;
            if (core == null) { why = "GameHelper.Core is null -- no session loaded"; return null; }
            var runner = core.EntityPlacementRunner;
            if (runner == null) { why = "IGameSessionManagers.EntityPlacementRunner is null"; return null; }
            var rt = runner.GetType();
            var f = rt.GetField("Map", BindingFlags.NonPublic | BindingFlags.Instance)
                 ?? rt.GetField("Map", BindingFlags.Public | BindingFlags.Instance);
            if (f == null)
            {
                var fields = string.Join(", ", rt.GetFields(BindingFlags.NonPublic | BindingFlags.Instance)
                                                 .Select(x => x.FieldType.Name + " " + x.Name));
                why = "no field 'Map' on " + rt.FullName + " -- the game changed. fields present: " + fields;
                return null;
            }
            var map = f.GetValue(runner);
            if (map == null) { why = "field 'Map' is null"; return null; }
            return map;
        }

        internal static string Status()
        {
            var lines = new List<string> { "ClaudeBridge " + ClaudeBridgeMod.Version };
            try
            {
                var core = GameHelper.Core;
                lines.Add("session managers : " + (core == null ? "NULL (load a save first)" : "ok"));
                if (core != null)
                {
                    lines.Add("placement runner : " + Describe(core.EntityPlacementRunner));
                    lines.Add("simulation speed : " + Describe(core.SimulationSpeed));
                    lines.Add("hub observer     : " + Describe(core.HubObserver));
                    lines.Add("shape registry   : " + Describe(core.ShapeRegistry));
                    lines.Add("research         : " + Describe(core.Research));
                }
                var map = GetMap(out var why);
                lines.Add(map != null ? "LIVE MAP         : REACHED " + map.GetType().FullName
                                      : "LIVE MAP         : UNREACHABLE " + why);
            }
            catch (Exception e) { lines.Add("EXCEPTION " + e.GetType().Name + ": " + e.Message); }
            return string.Join("\n", lines);
        }

        private static string Describe(object o) => o == null ? "null" : o.GetType().FullName;

        /// <summary>What the live map really offers, so the next stage is written
        /// against actual signatures instead of a guess.</summary>
        internal static string Inspect()
        {
            var map = GetMap(out var why);
            if (map == null) return "no live map: " + why;
            return Dump(map.GetType(), m => m.Name.StartsWith("Create") || m.Name.StartsWith("Delete")
                                         || m.Name.StartsWith("Finish") || m.Name.StartsWith("TryGet")
                                         || m.Name.StartsWith("Get"));
        }

        internal static string Members(string typeName)
        {
            if (string.IsNullOrEmpty(typeName)) return "ERROR: members <substring of a type name>";
            var hits = AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new Type[0]; } })
                .Where(t => t.FullName != null &&
                            t.FullName.IndexOf(typeName, StringComparison.OrdinalIgnoreCase) >= 0)
                .Take(12).ToList();
            if (hits.Count == 0) return "no type matching '" + typeName + "'";
            return string.Join("\n\n", hits.Select(t => Dump(t, _ => true)));
        }

        private static string Dump(Type t, Func<MethodInfo, bool> keep)
        {
            var lines = new List<string> { "=== " + t.FullName + "  [" + t.Assembly.GetName().Name + "]" };
            foreach (var i in t.GetInterfaces().OrderBy(x => x.FullName)) lines.Add("  : " + i.FullName);
            foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance).OrderBy(p => p.Name))
                lines.Add("  prop " + Sig(p.PropertyType) + " " + p.Name);
            foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.Instance)
                               .Where(m => !m.IsSpecialName && keep(m)).OrderBy(m => m.Name))
                lines.Add("  " + Sig(m.ReturnType) + " " + m.Name + "("
                          + string.Join(", ", m.GetParameters().Select(p =>
                                (p.ParameterType.IsByRef ? "ref " : "") + Sig(p.ParameterType) + " " + p.Name))
                          + ")");
            return string.Join("\n", lines);
        }

        private static string Sig(Type t)
        {
            if (t.IsByRef) t = t.GetElementType();
            return t.IsGenericType
                ? t.Name.Split('`')[0] + "<" + string.Join(",", t.GetGenericArguments().Select(Sig)) + ">"
                : t.Name;
        }
    }
}
