import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/globals.css";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("No se encontró el elemento #root en el DOM");

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>
);
