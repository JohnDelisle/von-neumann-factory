// spz2api -- read the REAL public API surface out of the Shapez 2 / Shapez Shifter
// assemblies, without running any of their code.
//
// This is the same move as tools/verify_mam.py: extract, never guess (PLAYBOOK).
// `MetadataLoadContext` loads assemblies for *reflection only*, so nothing executes
// and we do not need Unity or the game to be running.
//
//   dotnet run -- types   <pattern>   [asm-substring]   list matching type names
//   dotnet run -- members <full.Type.Name>              full signatures of one type
//   dotnet run -- asms                                  list every assembly we can see
//   dotnet run -- refs    <pattern>   [asm-substring]   who EXPOSES that type
//
// <pattern> is a case-insensitive substring, or /regex/.
using System.Reflection;
using System.Text.RegularExpressions;

var managed = Environment.GetEnvironmentVariable("SPZ2_PATH")
    ?? throw new Exception("SPZ2_PATH is not set -- run `shapez 2.exe --set-modding-env-vars`");
var shifter = Environment.GetEnvironmentVariable("SPZ2_SHIFTER");

var paths = new List<string>(Directory.GetFiles(managed, "*.dll"));
if (shifter is not null && File.Exists(shifter))
{
    // the Shifter and its MonoMod dependencies live beside it in the Workshop folder
    var dir = Path.GetDirectoryName(shifter)!;
    paths.AddRange(Directory.GetFiles(dir, "*.dll"));
    var workshop = Directory.GetParent(dir)!.FullName;
    foreach (var sub in Directory.GetDirectories(workshop))
        paths.AddRange(Directory.GetFiles(sub, "*.dll"));
}
paths.AddRange(Directory.GetFiles(Path.GetDirectoryName(typeof(object).Assembly.Location)!, "*.dll"));

var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
var unique = paths.Where(p => seen.Add(Path.GetFileName(p))).ToList();
using var mlc = new MetadataLoadContext(new PathAssemblyResolver(unique));

IEnumerable<Assembly> Load()
{
    foreach (var p in unique)
    {
        Assembly a; try { a = mlc.LoadFromAssemblyPath(p); } catch { continue; }
        yield return a;
    }
}

Func<string, bool> Matcher(string pat) =>
    pat.Length > 1 && pat.StartsWith('/') && pat.EndsWith('/')
        ? new Regex(pat[1..^1], RegexOptions.IgnoreCase).IsMatch
        : s => s.Contains(pat, StringComparison.OrdinalIgnoreCase);

string Sig(Type t) => t.IsGenericType
    ? t.Name.Split('`')[0] + "<" + string.Join(",", t.GetGenericArguments().Select(Sig)) + ">"
    : t.Name;

var cmd = args.Length > 0 ? args[0] : "asms";

if (cmd == "asms")
{
    foreach (var a in Load().OrderBy(a => a.GetName().Name))
    {
        int n; try { n = a.GetTypes().Length; } catch { continue; }
        Console.WriteLine($"{n,6}  {a.GetName().Name}");
    }
}
else if (cmd == "types")
{
    var match = Matcher(args[1]);
    var asmFilter = args.Length > 2 ? args[2] : null;
    foreach (var a in Load().OrderBy(a => a.GetName().Name))
    {
        var name = a.GetName().Name!;
        if (asmFilter is not null && !name.Contains(asmFilter, StringComparison.OrdinalIgnoreCase)) continue;
        Type[] ts; try { ts = a.GetTypes(); } catch { continue; }
        foreach (var t in ts.Where(t => t.FullName is not null && match(t.FullName)).OrderBy(t => t.FullName))
            Console.WriteLine($"{(t.IsInterface ? "interface" : t.IsEnum ? "enum" : t.IsAbstract && t.IsSealed ? "static  " : "class   ")}  {t.FullName}   [{name}]");
    }
}
else if (cmd == "refs")
{
    // WHO EXPOSES THIS TYPE?  `types` and `members` both need you to already know
    // the name of the thing that holds what you want.  The hard question is the
    // reverse one -- "I have a session, how do I reach an IMapModel from it" --
    // so this scans every member of every type for a signature mentioning the
    // pattern, and reports the holder.  Properties and parameterless getters first:
    // those are the reachable ones.
    var match = Matcher(args[1]);
    var asmFilter = args.Length > 2 ? args[2] : null;
    const BindingFlags F = BindingFlags.Public | BindingFlags.NonPublic
                         | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
    foreach (var a in Load().OrderBy(a => a.GetName().Name))
    {
        var an = a.GetName().Name!;
        if (asmFilter is not null && !an.Contains(asmFilter, StringComparison.OrdinalIgnoreCase)) continue;
        Type[] ts; try { ts = a.GetTypes(); } catch { continue; }
        foreach (var t in ts)
        {
            if (t.FullName is null) continue;
            var hits = new List<string>();
            try
            {
                foreach (var pr in t.GetProperties(F))
                    if (match(pr.PropertyType.FullName ?? pr.PropertyType.Name))
                        hits.Add($"    prop   {Sig(pr.PropertyType)} {pr.Name}");
                foreach (var fl in t.GetFields(F))
                    if (match(fl.FieldType.FullName ?? fl.FieldType.Name))
                        hits.Add($"    field  {(fl.IsPublic ? "" : "(private) ")}{Sig(fl.FieldType)} {fl.Name}");
                foreach (var m in t.GetMethods(F).Where(m => !m.IsSpecialName))
                {
                    var r = match(m.ReturnType.FullName ?? m.ReturnType.Name);
                    var ps = m.GetParameters();
                    var pin = ps.Any(x => match(x.ParameterType.FullName ?? x.ParameterType.Name));
                    if (r || pin)
                        hits.Add($"    {(r ? "RETURNS" : "takes  ")} {(m.IsStatic ? "static " : "")}{Sig(m.ReturnType)} {m.Name}("
                            + string.Join(", ", ps.Select(x => $"{Sig(x.ParameterType)} {x.Name}")) + ")");
                }
                foreach (var c in t.GetConstructors(F))
                    if (c.GetParameters().Any(x => match(x.ParameterType.FullName ?? x.ParameterType.Name)))
                        hits.Add($"    ctor   ({string.Join(", ", c.GetParameters().Select(x => $"{Sig(x.ParameterType)} {x.Name}"))})");
            }
            catch { continue; }
            if (hits.Count == 0) continue;
            Console.WriteLine();
            Console.WriteLine($"=== {t.FullName}  [{an}]");
            foreach (var h in hits.OrderBy(h => h)) Console.WriteLine(h);
        }
    }
}
else if (cmd == "members")
{
    var match = Matcher(args[1]);
    foreach (var a in Load())
    {
        Type[] ts; try { ts = a.GetTypes(); } catch { continue; }
        foreach (var t in ts.Where(t => t.FullName is not null && match(t.FullName)))
        {
            Console.WriteLine($"\n=== {t.FullName}  [{a.GetName().Name}]");
            foreach (var i in t.GetInterfaces()) Console.WriteLine($"    : {i.FullName}");
            foreach (var c in t.GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                Console.WriteLine($"    ctor {(c.IsPublic ? "" : "(private) ")}({string.Join(", ", c.GetParameters().Select(p => $"{Sig(p.ParameterType)} {p.Name}"))})");
            const BindingFlags F = BindingFlags.Public | BindingFlags.NonPublic
                                 | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
            foreach (var m in t.GetMethods(F).Where(m => !m.IsSpecialName).OrderBy(m => m.Name))
                Console.WriteLine($"    {(m.IsStatic ? "static " : "")}{Sig(m.ReturnType)} {m.Name}("
                    + string.Join(", ", m.GetParameters().Select(p => $"{Sig(p.ParameterType)} {p.Name}")) + ")");
            foreach (var p in t.GetProperties(F).OrderBy(p => p.Name))
                Console.WriteLine($"    prop {Sig(p.PropertyType)} {p.Name}");
            foreach (var f in t.GetFields(F).Where(f => f.IsPublic).OrderBy(f => f.Name))
                Console.WriteLine($"    field {Sig(f.FieldType)} {f.Name}");
        }
    }
}
