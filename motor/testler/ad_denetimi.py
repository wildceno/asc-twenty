"""Her modülü içe aktarır, tüm fonksiyonların bayt kodundaki global ad başvurularının tanımlı olduğunu denetler."""
import builtins, dis, importlib, os, pkgutil, sys, types
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ascendia_motor
hata = 0
def kodlar(c):
    yield c
    for k in c.co_consts:
        if isinstance(k, types.CodeType): yield from kodlar(k)
for m in pkgutil.walk_packages(ascendia_motor.__path__, "ascendia_motor."):
    if m.name.endswith("__main__"): continue
    mod = importlib.import_module(m.name)
    src = open(mod.__file__).read()
    for c in kodlar(compile(src, mod.__file__, "exec")):
        for ins in dis.get_instructions(c):
            if ins.opname in ("LOAD_GLOBAL", "LOAD_NAME") and ins.argval not in mod.__dict__ and not hasattr(builtins, ins.argval):
                print(f"TANIMSIZ {m.name}: {ins.argval} ({c.co_name})"); hata += 1
print("denetim:", "temiz" if not hata else f"{hata} sorun")
sys.exit(1 if hata else 0)
