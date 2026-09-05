// ClaudeBridge -- Stage 0: prove the hook, write nothing.
//
// The whole point of this stage is to answer one question in the running game:
// can a mod reach the live IMapModel?  Everything else -- placement, a JSON
// endpoint, an MCP wrapper -- is downstream of that, and none of it is worth
// writing until it is answered on John's machine rather than in the metadata.
//
// The chain, found with `tools/spz2api -- refs` against the installed assemblies:
//
//     ShapezShifter.Kit.GameHelper.Core          static property -> IGameSessionManagers
//       .EntityPlacementRunner                   public property -> IEntityPlacementRunner
//         private field "Map"                                    -> IMapModel
//
// NO method in any game assembly RETURNS an IMapModel; it is only ever passed in
// or held.  That is why it looked unreachable.  EntityPlacementRunner holds one.
//
// The field read is deliberately done by reflection rather than by casting to the
// concrete Game.Interaction.EntityPlacementRunner: it keeps this assembly's hard
// references down to three, and -- more importantly -- a game patch that renames
// the field then produces a clear diagnostic from `claudebridge.status` instead of
// a TypeLoadException at mod load.  A private field is the one genuinely fragile
// thing in this design, so it should fail loudly and in one identifiable place.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Game.Core.Modding;
using ShapezShifter.Flow;
using ShapezShifter.Kit;

namespace ClaudeBridge
{
    public sealed class ClaudeBridgeMod : IMod
    {
        private ModConsoleCommandsCreator.ModConsoleRewirer _console;

        public ClaudeBridgeMod()
        {
            // Shifter prefixes every command with the lowercased assembly name, so
            // these land as `claudebridge.status` and `claudebridge.inspect`.
            _console = ModConsoleCommandsCreator.AddModCommands(this);
            _console.AddCommand(c => c.Register("status", ctx => Say(ctx, Status()), false));
            _console.AddCommand(c => c.Register("inspect", ctx => Say(ctx, Inspect()), false));
        }

        public void Dispose() => _console?.Dispose();

        // ------------------------------------------------------------------ output
        // CommandContext's shape is not pinned down yet, so route every reply through
        // one place: whatever the console hands us, we find something callable that
        // takes a string. When Stage 1 replaces this with a real transport it is the
        // only method that has to change.
        private static void Say(object ctx, string text)
        {
            if (ctx == null) { Console.WriteLine(text); return; }
            var t = ctx.GetType();
            var m = t.GetMethods(BindingFlags.Public | BindingFlags.Instance)
                     .FirstOrDefault(x => (x.Name == "Print" || x.Name == "Log" || x.Name == "Output"
                                           || x.Name == "WriteLine" || x.Name == "Reply")
                                          && x.GetParameters().Length == 1
                                          && x.GetParameters()[0].ParameterType == typeof(string));
            if (m != null) { m.Invoke(ctx, new object[] { text }); return; }
            var p = t.GetProperties(BindingFlags.Public | BindingFlags.Instance)
                     .FirstOrDefault(x => typeof(Action<string>).IsAssignableFrom(x.PropertyType));
            if (p != null) { ((Action<string>)p.GetValue(ctx))(text); return; }
            Console.WriteLine(text);
        }

        // ------------------------------------------------------------- the one hop
        /// <summary>The live map, or null with `why` explaining exactly which step failed.</summary>
        private static object GetMap(out string why)
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
                why = "no field 'Map' on " + rt.FullName + " -- the game changed. fields: " + fields;
                return null;
            }
            var map = f.GetValue(runner);
            if (map == null) { why = "field 'Map' is null"; return null; }
            return map;
        }

        // -------------------------------------------------------------- commands
        private static string Status()
        {
            var lines = new List<string> { "ClaudeBridge 0.1.0 (stage 0, read-only)" };
            try
            {
                var core = GameHelper.Core;
                lines.Add("  session managers : " + (core == null ? "NULL (load a save first)" : "ok"));
                if (core != null)
                {
                    lines.Add("  placement runner : " + Describe(core.EntityPlacementRunner));
                    lines.Add("  simulation speed : " + Describe(core.SimulationSpeed));
                    lines.Add("  hub observer     : " + Describe(core.HubObserver));
                    lines.Add("  shape registry   : " + Describe(core.ShapeRegistry));
                }
                var map = GetMap(out var why);
                lines.Add(map != null
                    ? "  LIVE MAP         : REACHED -- " + map.GetType().FullName
                    : "  LIVE MAP         : unreachable -- " + why);
            }
            catch (Exception e)
            {
                lines.Add("  EXCEPTION " + e.GetType().Name + ": " + e.Message);
            }
            return string.Join("\n", lines);
        }

        private static string Describe(object o) => o == null ? "null" : o.GetType().Name;

        /// <summary>What the map object actually offers, so Stage 1 can be written against
        /// the real signatures instead of against a guess.</summary>
        private static string Inspect()
        {
            var map = GetMap(out var why);
            if (map == null) return "no live map: " + why;
            var t = map.GetType();
            var lines = new List<string> { "live map: " + t.FullName };
            foreach (var i in t.GetInterfaces().OrderBy(x => x.FullName))
                lines.Add("  : " + i.FullName);
            foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.Instance)
                               .Where(m => m.Name.StartsWith("Create") || m.Name.StartsWith("Delete")
                                        || m.Name.StartsWith("Finish") || m.Name.StartsWith("TryGet"))
                               .OrderBy(m => m.Name))
                lines.Add("  " + m.ReturnType.Name + " " + m.Name + "("
                          + string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name))
                          + ")");
            return string.Join("\n", lines);
        }
    }
}
