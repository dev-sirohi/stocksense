import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// React 18 root API — replaces the older ReactDOM.render().
// StrictMode renders components twice in development to catch side-effect bugs.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
