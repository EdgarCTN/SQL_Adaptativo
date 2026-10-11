import { createBrowserRouter, Navigate } from "react-router-dom";

import Pagina403 from "../features/errores/Pagina403";
import Pagina404 from "../features/errores/Pagina404";
import LoginPage from "../features/auth/LoginPage";
import RegistroPage from "../features/auth/RegistroPage";
import PerfilPage from "../features/perfil/PerfilPage";
import Layout from "./Layout";
import Raiz from "./Raiz";
import { RutaProtegida, RutaPublica } from "./RutaProtegida";

export const router = createBrowserRouter([
  {
    element: <Raiz />,
    errorElement: <Pagina404 mensaje="Ocurrió un problema al abrir esta pantalla." />,
    children: [
      { path: "/", element: <Navigate to="/perfil" replace /> },
      {
        element: <RutaPublica />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/registro", element: <RegistroPage /> },
        ],
      },
      {
        element: <RutaProtegida />,
        children: [{ element: <Layout />, children: [{ path: "/perfil", element: <PerfilPage /> }] }],
      },
      { path: "/403", element: <Pagina403 /> },
      { path: "*", element: <Pagina404 /> },
    ],
  },
]);
