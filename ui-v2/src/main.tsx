import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { installUiLogging, writeUiLog } from "./uiLogger";

installUiLogging();
writeUiLog("info", "Интерфейс запущен", "bootstrap");
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
