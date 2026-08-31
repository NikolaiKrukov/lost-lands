import React from "react";
import ReactDOM from "react-dom/client";
import { setWorkerUrl } from "maplibre-gl";
import App from "./App";
import "./styles.css";
import "maplibre-gl/dist/maplibre-gl.css";

setWorkerUrl("/assets/maplibre-gl-worker.mjs");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
