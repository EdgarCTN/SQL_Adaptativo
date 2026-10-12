import { createBrowserRouter } from "react-router-dom";

import ConsentimientoPage from "../features/diagnostico/ConsentimientoPage";
import DiagnosticoPage from "../features/diagnostico/DiagnosticoPage";
import DesafioPage from "../features/desafios/DesafioPage";
import DesafiosPage from "../features/desafios/DesafiosPage";
import Pagina403 from "../features/errores/Pagina403";
import Pagina404 from "../features/errores/Pagina404";
import LoginPage from "../features/auth/LoginPage";
import RegistroPage from "../features/auth/RegistroPage";
import PerfilPage from "../features/perfil/PerfilPage";
import Inicio from "./Inicio";
import Layout from "./Layout";
import Raiz from "./Raiz";
import { RutaProtegida, RutaPublica } from "./RutaProtegida";

export const router = createBrowserRouter([
  {
    element: <Raiz />,
    errorElement: <Pagina404 mensaje="Ocurrió un problema al abrir esta pantalla." />,
    children: [
      {
        element: <RutaPublica />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/registro", element: <RegistroPage /> },
        ],
      },
      {
        element: <RutaProtegida />,
        children: [
          { path: "/", element: <Inicio /> },
          {
            element: <Layout />,
            children: [
              { path: "/perfil", element: <PerfilPage /> },
              {
                element: <RutaProtegida roles={["estudiante"]} />,
                children: [
                  { path: "/desafios", element: <DesafiosPage /> },
                  { path: "/desafios/:id", element: <DesafioPage /> },
                ],
              },
            ],
          },
        ],
      },
      {
        element: <RutaProtegida roles={["estudiante"]} />,
        children: [
          { path: "/consentimiento", element: <ConsentimientoPage /> },
          { path: "/diagnostico", element: <DiagnosticoPage /> },
        ],
      },
      { path: "/403", element: <Pagina403 /> },
      { path: "*", element: <Pagina404 /> },
    ],
  },
]);
