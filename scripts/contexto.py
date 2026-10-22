"""Genera un resumen compacto del proyecto para pegarlo a Claude (ahorra tokens).

Uso (desde la raiz del proyecto):
  python scripts/contexto.py                 -> lista los modulos disponibles
  python scripts/contexto.py desafios auth   -> resumen de esos modulos del backend
  python scripts/contexto.py core modelos    -> core y todas las tablas
  python scripts/contexto.py frontend        -> rutas y API del frontend
  python scripts/contexto.py desafios --guardar   -> escribe docs/CONTEXTO_SALIDA.md
Sin dependencias externas.
"""
import ast
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "backend" / "app"
FRONT = RAIZ / "frontend" / "src"


def firma(nodo):
    a = nodo.args
    nombres = [x.arg for x in a.posonlyargs + a.args if x.arg not in ("self", "cls")]
    nombres += ["*" + a.vararg.arg] if a.vararg else []
    nombres += [x.arg for x in a.kwonlyargs]
    nombres += ["**" + a.kwarg.arg] if a.kwarg else []
    ret = f" -> {ast.unparse(nodo.returns)}" if nodo.returns else ""
    return f"({', '.join(nombres)}){ret}"


def primera_linea(nodo):
    d = ast.get_docstring(nodo)
    return (" # " + d.splitlines()[0][:90]) if d else ""


def resumen_py(ruta: Path) -> list[str]:
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return [f"  (no se pudo leer {ruta.name})"]
    sal = []
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rutas = [ast.unparse(d) for d in n.decorator_list if re.match(r"\w+\.(get|post|put|delete|patch)\(", ast.unparse(d))]
            if rutas:
                sal.append(f"  {rutas[0]}  -> {n.name}{firma(n)}")
            elif not n.name.startswith("_"):
                sal.append(f"  def {n.name}{firma(n)}{primera_linea(n)}")
        elif isinstance(n, ast.ClassDef):
            cols = []
            metodos = []
            for m in n.body:
                if isinstance(m, ast.AnnAssign) and isinstance(m.target, ast.Name) and m.value is not None:
                    txt = ast.unparse(m.value)
                    if "mapped_column" in txt or "relationship" in txt:
                        extra = re.findall(r"ForeignKey\(['\"]([^'\"]+)", txt)
                        cols.append(m.target.id + (f"->{extra[0]}" if extra else ""))
                elif isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                    metodos.append(m.name + firma(m))
            tabla = ""
            for m in n.body:
                if isinstance(m, ast.Assign) and any(getattr(t, "id", "") == "__tablename__" for t in m.targets):
                    tabla = f" [tabla {ast.unparse(m.value)}]"
            if cols:
                sal.append(f"  class {n.name}{tabla}: {', '.join(cols)}")
            else:
                sal.append(f"  class {n.name}{primera_linea(n)}" + (f"  metodos: {'; '.join(metodos[:8])}" if metodos else ""))
    return sal


def modulo_backend(nombre: str) -> list[str]:
    base = APP / ("modules/" + nombre if (APP / "modules" / nombre).is_dir() else nombre)
    if not base.is_dir():
        return [f"## {nombre}: no existe"]
    sal = [f"## backend/{base.relative_to(RAIZ / 'backend').as_posix()}"]
    for f in sorted(base.rglob("*.py")):
        if f.name == "__init__.py" or "__pycache__" in f.parts:
            continue
        r = resumen_py(f)
        if r:
            sal.append(f" {f.relative_to(base).as_posix()}")
            sal += r
    return sal


def modelos() -> list[str]:
    sal = ["## Tablas (todos los models.py)"]
    for f in sorted(APP.rglob("models.py")):
        for l in resumen_py(f):
            if l.strip().startswith("class") and "[tabla" in l:
                sal.append(l.strip())
    return sal


def frontend() -> list[str]:
    sal = ["## frontend/src"]
    router = FRONT / "app" / "router.tsx"
    if router.exists():
        t = router.read_text(encoding="utf-8")
        sal.append(" rutas: " + ", ".join(sorted(set(re.findall(r"path:\s*['\"]([^'\"]+)", t)))))
    enlaces = FRONT / "app" / "Layout.tsx"
    if enlaces.exists():
        sal.append(" menu (Layout.tsx): " + ", ".join(re.findall(r"etiqueta:\s*['\"]([^'\"]+)", enlaces.read_text(encoding="utf-8"))))
    api = FRONT / "api"
    if api.is_dir():
        sal.append(" api/:")
        for f in sorted(api.glob("*.ts")):
            ex = re.findall(r"export (?:async )?(?:function|const) (\w+)", f.read_text(encoding="utf-8"))
            if ex:
                sal.append(f"   {f.name}: {', '.join(ex)}")
    feat = FRONT / "features"
    if feat.is_dir():
        sal.append(" features/:")
        for d in sorted(p for p in feat.iterdir() if p.is_dir()):
            sal.append(f"   {d.name}: {', '.join(x.stem for x in sorted(d.glob('*.ts*')))}")
    return sal


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    guardar = "--guardar" in sys.argv
    mods = sorted(p.name for p in (APP / "modules").iterdir() if p.is_dir() and p.name != "__pycache__")
    if not args:
        print("Modulos:", ", ".join(mods), "| core | modelos | frontend")
        return
    sal = []
    for a in args:
        if a == "modelos":
            sal += modelos()
        elif a == "frontend":
            sal += frontend()
        else:
            sal += modulo_backend(a)
    texto = "\n".join(sal)
    if guardar:
        destino = RAIZ / "docs" / "CONTEXTO_SALIDA.md"
        destino.parent.mkdir(exist_ok=True)
        destino.write_text(texto + "\n", encoding="utf-8")
        print("Escrito", destino.relative_to(RAIZ))
    else:
        print(texto)


if __name__ == "__main__":
    main()
