import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { installNetworkLogging } from "./logStore";

installNetworkLogging();
const root = document.getElementById("root");
if (!root) throw new Error("Root element was not found");

createRoot(root).render(<StrictMode><App /></StrictMode>);
