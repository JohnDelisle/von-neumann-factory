// Reflect.cs -- the escape hatch.
//
// Every verb hard-coded into this mod is a guess about what will turn out to matter,
// and every wrong guess costs a rebuild AND a game restart -- which, with no
// command-line way to load a savegame, is the single most expensive operation in
// this whole setup.  So the mod ships a small general evaluator instead: name any
// type, walk any property or field, invoke any method, from the LIVE process.
//
//     get   core.SimulationSpeed.Speed
//     set   core.SimulationSpeed.Speed 5
//     call  map.GetIsland(...)                 (simple scalar args only)
//     find  GameOrchestrator                   locate live instances, bind to $0, $1
//     type  Game.Orchestration.GameOrchestrator    static members
//
// Roots: `core` = GameHelper.Core, `map` = the live IMapModel, `$n` = anything a
// previous `find` bound.  Arguments parse as bool / int / float / quoted string, and
// anything else is passed as a string; that covers most of what is worth reaching
// and refuses to become a scripting language.
//
// This is deliberately powerful and deliberately unsafe -- it can call anything the
// game can call. It is not exposed to a network; it reads files from a folder on
// John's own machine, and the whole mod is opt-in and off unless installed.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Text;

namespace ClaudeBridge
{
    internal static class Reflect
    {
        internal static readonly List<object> Bound = new List<object>();

        private const BindingFlags Any = BindingFlags.Public | BindingFlags.NonPublic
                                       | BindingFlags.Instance | BindingFlags.Static;

        // ------------------------------------------------------------------ roots
        private static object Root(string name, out string err)
        {
            err = null;
            if (name == "core")
            {
                var c = ShapezShifter.Kit.GameHelper.Core;
                if (c == null) err = "GameHelper.Core is null (no session loaded)";
                return c;
            }
            if (name == "map") return Api.GetMap(out err);
            if (name.StartsWith("$"))
            {
                if (int.TryParse(name.Substring(1), out var i) && i >= 0 && i < Bound.Count)
                    return Bound[i];
                err = name + " is not bound -- run `find` first";
                return null;
            }
            err = "unknown root '" + name + "'. roots: core, map, $0..$" + Math.Max(0, Bound.Count - 1);
            return null;
        }

        /// <summary>Walk a dotted path. Returns the value, or null with `err` set.
        ///
        /// The first segment is a root (`core`, `map`, `$n`); failing that, the LONGEST
        /// prefix that names a type is taken as a static context, so
        /// `Game.Orchestration.GameBootstrapper.GameOrchestrator` works.  That case is
        /// not a nicety: GameBootstrapper is a static class, which means it is also an
        /// abstract one, which means `find` skips it -- and it is the only holder of
        /// the GameOrchestrator, the object that can load a savegame.</summary>
        internal static object Resolve(string path, out string err)
        {
            err = null;
            var parts = path.Split('.');
            object cur;
            int next;

            if (parts[0] == "core" || parts[0] == "map" || parts[0].StartsWith("$"))
            {
                cur = Root(parts[0], out err);
                if (err != null) return null;
                next = 1;
            }
            else
            {
                Type t = null; var used = 0;
                for (var n = parts.Length; n >= 1; n--)
                {
                    t = FindType(string.Join(".", parts.Take(n).ToArray()));
                    if (t != null) { used = n; break; }
                }
                if (t == null)
                {
                    err = "'" + parts[0] + "' is not a root (core, map, $n) and no prefix of '"
                        + path + "' names a type";
                    return null;
                }
                if (used == parts.Length) return t;              // the Type itself
                cur = StaticMember(t, parts[used], out err);
                if (err != null) return null;
                next = used + 1;
            }

            for (var i = next; i < parts.Length; i++)
            {
                if (cur == null) { err = "null before '" + parts[i] + "'"; return null; }
                cur = Member(cur, parts[i], out err);
                if (err != null) return null;
            }
            return cur;
        }

        internal static Type FindType(string name)
        {
            foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type[] ts;
                try { ts = a.GetTypes(); } catch { continue; }
                foreach (var t in ts)
                    if (t.FullName == name || t.Name == name) return t;
            }
            return null;
        }

        private static object StaticMember(Type t, string name, out string err)
        {
            err = null;
            var p = t.GetProperty(name, Any);
            if (p != null && p.CanRead) return p.GetValue(null);
            var f = t.GetField(name, Any);
            if (f != null) return f.GetValue(null);
            err = "no static member '" + name + "' on " + t.FullName + ". has: "
                + string.Join(", ", t.GetProperties(Any).Select(x => x.Name)
                                     .Concat(t.GetFields(Any).Select(x => x.Name)).Distinct().Take(40));
            return null;
        }

        /// <summary>Every static member of a type, with values. The main-menu process has
        /// no console commands registered at all, so statics are the only way in.</summary>
        internal static string Statics(string typeName)
        {
            var t = FindType(typeName);
            if (t == null) return "no type '" + typeName + "'";
            var sb = new StringBuilder("=== " + t.FullName + "  [" + t.Assembly.GetName().Name + "]\n");
            foreach (var f in t.GetFields(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
            {
                object v; try { v = f.GetValue(null); } catch (Exception e) { v = "<" + e.GetType().Name + ">"; }
                sb.Append("  field ").Append(f.FieldType.Name).Append(' ').Append(f.Name)
                  .Append(" = ").Append(v == null ? "null" : v.ToString()).Append('\n');
            }
            foreach (var p in t.GetProperties(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
            {
                object v; try { v = p.GetValue(null); } catch (Exception e) { v = "<" + e.GetType().Name + ">"; }
                sb.Append("  prop  ").Append(p.PropertyType.Name).Append(' ').Append(p.Name)
                  .Append(" = ").Append(v == null ? "null" : v.ToString()).Append('\n');
            }
            foreach (var m in t.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
                               .Where(m => !m.IsSpecialName))
                sb.Append("  static ").Append(m.ReturnType.Name).Append(' ').Append(m.Name).Append('(')
                  .Append(string.Join(", ", m.GetParameters().Select(x => x.ParameterType.Name + " " + x.Name)))
                  .Append(")\n");
            return sb.ToString().TrimEnd();
        }

        private static object Member(object target, string name, out string err)
        {
            err = null;
            var t = target.GetType();
            for (var ty = t; ty != null; ty = ty.BaseType)
            {
                var p = ty.GetProperty(name, Any);
                if (p != null && p.CanRead) return p.GetValue(target);
                var f = ty.GetField(name, Any);
                if (f != null) return f.GetValue(target);
            }
            foreach (var i in t.GetInterfaces())
            {
                var p = i.GetProperty(name, Any);
                if (p != null && p.CanRead) return p.GetValue(target);
            }
            err = "no member '" + name + "' on " + t.FullName + ". has: "
                + string.Join(", ", t.GetProperties(Any).Select(x => x.Name)
                                     .Concat(t.GetFields(Any).Select(x => x.Name)).Distinct().Take(40));
            return null;
        }

        internal static string Get(string path)
        {
            var v = Resolve(path, out var err);
            return err != null ? "ERROR " + err : Show(v);
        }

        internal static string Set(string path, string raw)
        {
            var dot = path.LastIndexOf('.');
            if (dot < 0) return "ERROR set needs a dotted path";
            var owner = Resolve(path.Substring(0, dot), out var err);
            if (err != null) return "ERROR " + err;
            if (owner == null) return "ERROR " + path.Substring(0, dot) + " is null";
            var name = path.Substring(dot + 1);
            for (var ty = owner.GetType(); ty != null; ty = ty.BaseType)
            {
                var p = ty.GetProperty(name, Any);
                if (p != null && p.CanWrite)
                {
                    p.SetValue(owner, Coerce(raw, p.PropertyType));
                    return path + " = " + Show(p.GetValue(owner));
                }
                var f = ty.GetField(name, Any);
                if (f != null)
                {
                    f.SetValue(owner, Coerce(raw, f.FieldType));
                    return path + " = " + Show(f.GetValue(owner));
                }
            }
            return "ERROR no settable '" + name + "' on " + owner.GetType().FullName;
        }

        /// <summary>call path.Method arg1 arg2 ...</summary>
        internal static string Call(string path, string[] args)
        {
            var dot = path.LastIndexOf('.');
            if (dot < 0) return "ERROR call needs <path>.<Method>";
            var owner = Resolve(path.Substring(0, dot), out var err);
            if (err != null) return "ERROR " + err;
            if (owner == null) return "ERROR receiver is null";
            var name = path.Substring(dot + 1);
            var cands = AllMethods(owner.GetType(), name, args.Length);
            if (cands.Count == 0)
                return "ERROR no method '" + name + "' taking " + args.Length + " args on "
                     + owner.GetType().FullName + ". candidates: "
                     + string.Join(", ", AllMethods(owner.GetType(), name, -1)
                           .Select(m => m.Name + "/" + m.GetParameters().Length));
            var m2 = cands[0];
            var ps = m2.GetParameters();
            var vals = new object[ps.Length];
            for (var i = 0; i < ps.Length; i++) vals[i] = Coerce(args[i], ps[i].ParameterType);
            var r = m2.Invoke(owner, vals);
            return m2.Name + " -> " + Show(r);
        }

        private static List<MethodInfo> AllMethods(Type t, string name, int argc)
        {
            var outp = new List<MethodInfo>();
            for (var ty = t; ty != null; ty = ty.BaseType)
                outp.AddRange(ty.GetMethods(Any).Where(m => m.Name == name
                                                    && (argc < 0 || m.GetParameters().Length == argc)));
            foreach (var i in t.GetInterfaces())
                outp.AddRange(i.GetMethods(Any).Where(m => m.Name == name
                                                    && (argc < 0 || m.GetParameters().Length == argc)));
            return outp;
        }

        private static object Coerce(string s, Type t)
        {
            if (t == typeof(string)) return s;
            if (t.IsEnum) return Enum.Parse(t, s, true);
            if (t == typeof(bool)) return bool.Parse(s);
            if (t == typeof(int)) return int.Parse(s, CultureInfo.InvariantCulture);
            if (t == typeof(short)) return short.Parse(s, CultureInfo.InvariantCulture);
            if (t == typeof(long)) return long.Parse(s, CultureInfo.InvariantCulture);
            if (t == typeof(float)) return float.Parse(s, CultureInfo.InvariantCulture);
            if (t == typeof(double)) return double.Parse(s, CultureInfo.InvariantCulture);
            if (s.StartsWith("$"))
            {
                if (int.TryParse(s.Substring(1), out var i) && i >= 0 && i < Bound.Count) return Bound[i];
            }
            if (s == "null") return null;
            return Convert.ChangeType(s, t, CultureInfo.InvariantCulture);
        }

        /// <summary>Ask the game's own DI container for a service.
        ///
        /// This is the right way to reach almost everything, and it took a while to
        /// notice.  `find` only sees UnityEngine.Objects; a sweep of static fields only
        /// sees singletons someone chose to make static.  But the game builds its
        /// services into Core.Dependency.DependencyContainer, reachable at
        /// GameBootstrapper.GameOrchestrator.InitializationDependencyContainer, whose
        /// BoundInstancesByResolveType maps type -> instance.  Containers nest, so this
        /// walks Children too -- the session's services live in a child of the
        /// initialization container, not in it.</summary>
        internal static object ResolveService(string typeName, out string err)
        {
            err = null;
            var root = Resolve("Game.Orchestration.GameBootstrapper.GameOrchestrator."
                             + "InitializationDependencyContainer", out err);
            if (root == null) { err = "no DependencyContainer: " + err; return null; }

            var wanted = FindType(typeName);
            if (wanted == null) { err = "no type '" + typeName + "'"; return null; }

            var seen = new HashSet<object>();
            var queue = new Queue<object>();
            queue.Enqueue(root);
            while (queue.Count > 0)
            {
                var c = queue.Dequeue();
                if (c == null || !seen.Add(c)) continue;
                var bound = Member(c, "BoundInstancesByResolveType", out _) as IDictionary;
                if (bound != null)
                    foreach (DictionaryEntry e in bound)
                        if (e.Value != null && wanted.IsInstanceOfType(e.Value))
                            return e.Value;
                if (Member(c, "Children", out _) is IEnumerable kids)
                    foreach (var k in kids) queue.Enqueue(k);
            }
            err = "nothing bound to " + wanted.FullName + " in the container tree";
            return null;
        }

        internal static string ResolveReport(string typeName)
        {
            var v = ResolveService(typeName, out var err);
            return v == null ? "ERROR " + err : Show(v);
        }

        /// <summary>Locate live instances of a type and bind them to $0, $1, ...</summary>
        internal static string Find(string typeName)
        {
            if (string.IsNullOrEmpty(typeName)) return "ERROR find <type substring>";
            var types = AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new Type[0]; } })
                .Where(t => t.FullName != null && !t.IsAbstract && !t.IsInterface
                            && t.FullName.IndexOf(typeName, StringComparison.OrdinalIgnoreCase) >= 0)
                .Take(20).ToList();
            if (types.Count == 0) return "no concrete type matching '" + typeName + "'";

            var sb = new StringBuilder();
            var unityObject = Type.GetType("UnityEngine.Object, UnityEngine.CoreModule");
            var resources = Type.GetType("UnityEngine.Resources, UnityEngine.CoreModule");
            var findAll = resources?.GetMethod("FindObjectsOfTypeAll", new[] { typeof(Type) });

            foreach (var t in types)
            {
                sb.Append(t.FullName).Append("  [").Append(t.Assembly.GetName().Name).Append("]");
                if (findAll != null && unityObject != null && unityObject.IsAssignableFrom(t))
                {
                    var arr = (Array)findAll.Invoke(null, new object[] { t });
                    sb.Append("  -> ").Append(arr.Length).Append(" live");
                    foreach (var o in arr.Cast<object>().Take(4))
                    {
                        Bound.Add(o);
                        sb.Append("  $").Append(Bound.Count - 1);
                    }
                }
                else sb.Append("  (not a UnityEngine.Object -- cannot scan)");
                sb.Append('\n');
            }
            return sb.ToString().TrimEnd();
        }

        internal static string Show(object v)
        {
            if (v == null) return "null";
            var t = v.GetType();
            if (v is string s) return "\"" + s + "\"";
            if (t.IsPrimitive || t.IsEnum) return v + "  (" + t.Name + ")";
            if (v is IEnumerable en && !(v is string))
            {
                var items = en.Cast<object>().Take(25).Select(x => x?.ToString() ?? "null").ToList();
                return t.Name + " [" + items.Count + (items.Count == 25 ? "+" : "") + "]\n  "
                     + string.Join("\n  ", items);
            }
            var bound = Bound.IndexOf(v);
            if (bound < 0) { Bound.Add(v); bound = Bound.Count - 1; }
            return t.FullName + "  bound to $" + bound + "\n  " + v;
        }
    }
}
