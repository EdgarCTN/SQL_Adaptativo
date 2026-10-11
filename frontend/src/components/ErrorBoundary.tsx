import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface Estado {
  fallo: boolean;
}

export default class ErrorBoundary extends Component<Props, Estado> {
  state: Estado = { fallo: false };

  static getDerivedStateFromError(): Estado {
    return { fallo: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Error de interfaz:", error, info.componentStack);
  }

  render() {
    if (!this.state.fallo) return this.props.children;
    return (
      <div role="alert" className="mx-auto mt-16 max-w-md rounded-xl border border-red-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Algo no salió como esperábamos</h1>
        <p className="mt-2 text-sm text-slate-600">
          Ocurrió un problema inesperado en esta pantalla. Puedes intentarlo de nuevo o recargar la página.
        </p>
        <div className="mt-4 flex justify-center gap-3">
          <button
            type="button"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            onClick={() => this.setState({ fallo: false })}
          >
            Intentar de nuevo
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            onClick={() => window.location.reload()}
          >
            Recargar página
          </button>
        </div>
      </div>
    );
  }
}
