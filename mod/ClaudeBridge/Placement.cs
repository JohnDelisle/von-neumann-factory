// Placement.cs -- write to the LIVE world.
//
// COORDINATES.  IMapModel speaks GlobalTileCoordinate, and the relationship to the
// savegame's island/cell pair was read off a machine already standing in the world
// rather than guessed:
//
//     BeltPortSenderInternalVariant@(GlobalTileCoordinate(42, 8, 0);Rotate180)
//
// is the west-edge sender of the miner on island (2,0) at local cell (2,8).  So
//
//     global = island * 20 + local cell            (20 tiles per island tile)
//
// and savegame rotation R2 renders as GridRotation.Rotate180.  Both halves of the
// project therefore address the same world, which is what lets a machine designed
// offline with save_world.py be placed live, and lets a live placement be verified
// by reading the save back.
//
// VALIDATION.  IMapModel.CreateBuilding is the raw creation call, underneath the
// interactive placement pipeline -- it does not check affordability, unlocks, or
// (as far as we can tell) collisions.  That makes it exactly what an agent wants
// and also makes our own checks the only thing between a generator bug and a
// corrupted map, so `place` refuses a cell that is already occupied and reports
// what is there instead.

using System;
using System.Linq;
using System.Reflection;
using ShapezShifter.Kit;

namespace ClaudeBridge
{
    internal static class Placement
    {
        private const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
                                       | BindingFlags.Instance | BindingFlags.Static;
        internal const int TilesPerIsland = 20;

        private static object _resolver;

        /// <summary>The building resolver.
        ///
        /// Three routes were tried and only the last one works, which is worth writing
        /// down because the first two are the obvious ones.  It is not in any static
        /// field, and it is not a UnityEngine.Object, so a static sweep and an object
        /// scan both come back empty.  It is not in the DI container either -- the
        /// initialization container has no children, so the session's services never
        /// appear there.  It hangs off the GameMode:
        ///
        ///     GameBootstrapper.GameOrchestrator.CurrentSubOrchestrator.Mode.Buildings
        ///
        /// which is a GameBuildings, and GameBuildings is the IGameBuildingsRegistry
        /// (hence an IBuildingResolver).  The DI route is kept as a fallback in case a
        /// future version binds it after all.</summary>
        private static readonly string[] ResolverPaths =
        {
            "Game.Orchestration.GameBootstrapper.GameOrchestrator.CurrentSubOrchestrator.Mode.Buildings",
        };

        private static object Resolver(out string err)
        {
            err = null;
            if (_resolver != null) return _resolver;
            foreach (var p in ResolverPaths)
            {
                var v = Reflect.Resolve(p, out var e);
                if (v != null && HasTryGetDefinition(v)) return _resolver = v;
                if (err == null) err = p + ": " + (e ?? "not a resolver");
            }
            var r = Reflect.ResolveService("Game.Core.Logic.IBuildingResolver", out var e2);
            if (r != null) return _resolver = r;
            err = err + "; container: " + e2;
            return null;
        }

        private static bool HasTryGetDefinition(object o) =>
            o.GetType().GetMethods(Any).Any(m => m.Name == "TryGetDefinition"
                                              && m.GetParameters().Length == 2);

        private static readonly string NL = ((char)10).ToString();

        private static object Coord(int x, int y, int z)
        {
            var t = Reflect.FindType("Game.Core.Coordinates.GlobalTileCoordinate");
            var c = t.GetConstructors(Any).First(k => k.GetParameters().Length == 3);
            return c.Invoke(new object[] { x, y, (short)z });
        }

        private static object Transform(int x, int y, int z, string rot, out string err)
        {
            err = null;
            // GridRotation is a STRUCT with static readonly fields, not an enum, so
            // Enum.Parse does not apply -- the values are NoRotate / RotateCW /
            // Rotate180 / RotateCCW, which is also the order the savegame's R 0..3 uses.
            var rotT = Reflect.FindType("Game.Core.Coordinates.GridRotation");
            if (rotT == null) { err = "GridRotation not found"; return null; }
            var rf = rotT.GetField(rot, BindingFlags.Static | BindingFlags.Public)
                  ?? rotT.GetFields(BindingFlags.Static | BindingFlags.Public)
                         .FirstOrDefault(f => f.FieldType == rotT
                             && string.Equals(f.Name, rot, StringComparison.OrdinalIgnoreCase));
            if (rf == null)
            {
                err = "bad rotation '" + rot + "'. values: " + string.Join(", ",
                        rotT.GetFields(BindingFlags.Static | BindingFlags.Public)
                            .Where(f => f.FieldType == rotT).Select(f => f.Name));
                return null;
            }
            var r = rf.GetValue(null);
            var tt = Reflect.FindType("Game.Core.Coordinates.GlobalTileTransform");
            var ctor = tt.GetConstructors(Any).First(k => k.GetParameters().Length == 2);
            return ctor.Invoke(new[] { Coord(x, y, z), r });
        }

        internal static string Rotations()
        {
            var rotT = Reflect.FindType("Game.Core.Coordinates.GridRotation");
            if (rotT == null) return "GridRotation not found";
            return string.Join("\n", rotT.GetFields(BindingFlags.Static | BindingFlags.Public)
                     .Where(f => f.FieldType == rotT)
                     .Select((f, i) => i + "  " + f.Name));
        }

        /// <summary>What stands at a global tile.</summary>
        internal static string At(int x, int y, int z)
        {
            var map = Api.GetMap(out var err);
            if (map == null) return "ERROR " + err;
            // TryGetBuilding, not GetBuilding: the latter throws on a tile that belongs
            // to no island, which is a DIFFERENT answer from "this cell is free" and must
            // not be confused with it before writing.
            var get = map.GetType().GetMethods(Any)
                .FirstOrDefault(m => m.Name == "TryGetBuilding" && m.GetParameters().Length == 2
                                  && m.GetParameters()[0].ParameterType.Name.StartsWith("GlobalTileCoordinate"));
            if (get == null) return "ERROR no TryGetBuilding(GlobalTileCoordinate, ref)";
            // GetBuilding throws rather than returning null when the tile belongs to no
            // island at all, which is a different answer from "there is nothing here".
            try
            {
                var args = new object[] { Coord(x, y, z), null };
                var found = (bool)get.Invoke(map, args);
                return found && args[1] != null ? args[1].ToString() : "empty";
            }
            catch (Exception e)
            {
                var inner = e;
                while (inner is TargetInvocationException && inner.InnerException != null)
                    inner = inner.InnerException;
                return "NOTILE (" + inner.GetType().Name + ": " + inner.Message + ")";
            }
        }

        /// <summary>What resource, if any, the game thinks is under an ISLAND tile.
        /// GetResourceAt_GC takes a GlobalChunkCoordinate -- "chunk" here means one
        /// island tile, the same unit resource-chunks.bin uses.</summary>
        internal static string Resource(int ix, int iy, int iz)
        {
            var map = Api.GetMap(out var err);
            if (map == null) return "ERROR " + err;
            var acc = Reflect.Resolve("map.ResourcesAccessor", out err);
            if (acc == null) return "ERROR ResourcesAccessor: " + err;
            var gcT = Reflect.FindType("Game.Core.Coordinates.GlobalChunkCoordinate");
            if (gcT == null) return "ERROR GlobalChunkCoordinate not found";
            var ctor = gcT.GetConstructors(Any).FirstOrDefault(c => c.GetParameters().Length == 3);
            if (ctor == null) return "ERROR no 3-arg GlobalChunkCoordinate ctor: "
                + string.Join(" | ", gcT.GetConstructors(Any).Select(c => c.GetParameters().Length
                    + ": " + string.Join(",", c.GetParameters().Select(p => p.ParameterType.Name))));
            var ps = ctor.GetParameters();
            object Conv(int v, Type t) => t == typeof(short) ? (object)(short)v : v;
            var gc = ctor.Invoke(new[] { Conv(ix, ps[0].ParameterType),
                                         Conv(iy, ps[1].ParameterType),
                                         Conv(iz, ps[2].ParameterType) });
            var m = acc.GetType().GetMethods(Any).FirstOrDefault(x => x.Name == "GetResourceAt_GC");
            if (m == null) return "ERROR no GetResourceAt_GC on " + acc.GetType().FullName;
            var args = new[] { gc };
            var r = m.Invoke(acc, args);
            if (r == null) return "no resource at island (" + ix + "," + iy + ")";
            var sb = new System.Text.StringBuilder(r.GetType().FullName + NL);
            foreach (var p in r.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
            {
                object v; try { v = p.GetValue(r); } catch (Exception e) { v = "<" + e.GetType().Name + ">"; }
                sb.Append("  ").Append(p.Name).Append(" = ").Append(v).Append(NL);
            }
            return sb.ToString().TrimEnd();
        }

        /// <summary>place &lt;variantId&gt; &lt;gx&gt; &lt;gy&gt; &lt;gz&gt; &lt;rotation&gt;</summary>
        internal static string Place(string[] a)
        {
            if (a.Length < 5)
                return "ERROR place <variantId> <globalX> <globalY> <z> <rotation>\n"
                     + "  global tile = island * 20 + local cell\n" + Rotations();

            var map = Api.GetMap(out var err);
            if (map == null) return "ERROR " + err;

            var existing = At(int.Parse(a[1]), int.Parse(a[2]), int.Parse(a[3]));
            if (existing != "empty")
                return "REFUSED: (" + a[1] + "," + a[2] + "," + a[3] + ") already holds " + existing;

            var resolver = Resolver(out err);
            if (resolver == null) return "ERROR " + err;

            var idT = Reflect.FindType("BuildingDefinitionId");
            var id = idT.GetConstructors(Any).First(c => c.GetParameters().Length == 1)
                        .Invoke(new object[] { a[0] });
            var tryGet = resolver.GetType().GetMethods(Any)
                .FirstOrDefault(m => m.Name == "TryGetDefinition" && m.GetParameters().Length == 2);
            if (tryGet == null) return "ERROR no TryGetDefinition on " + resolver.GetType().FullName;
            var gargs = new object[] { id, null };
            if (!(bool)tryGet.Invoke(resolver, gargs))
                return "ERROR no building definition '" + a[0] + "'";
            var definition = gargs[1];

            var transform = Transform(int.Parse(a[1]), int.Parse(a[2]), int.Parse(a[3]), a[4], out err);
            if (transform == null) return "ERROR " + err;

            var create = map.GetType().GetMethods(Any)
                .FirstOrDefault(m => m.Name == "CreateBuilding" && m.GetParameters().Length == 3);
            if (create == null) return "ERROR no 3-arg CreateBuilding";
            var cargs = new[] { definition, transform, null };   // configuration: none
            object built;
            try { built = create.Invoke(map, cargs); }
            catch (Exception e)
            {
                var inner = e; while (inner is TargetInvocationException && inner.InnerException != null)
                    inner = inner.InnerException;
                return "ERROR CreateBuilding threw " + inner.GetType().Name + ": " + inner.Message;
            }
            return built == null ? "CreateBuilding returned null" : "placed " + built;
        }
    }
}
