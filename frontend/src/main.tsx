import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { calentarServidor } from "./api/servidor";
import { router } from "./app/router";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";

// Calentamiento proactivo: el servidor gratuito empieza a despertar apenas se abre la página.
void calentarServidor();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <RouterProvider router={router} />
    </ErrorBoundary>
  </React.StrictMode>
);
