import { createRoot } from "react-dom/client";
import "@fontsource-variable/manrope";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./styles.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<App />);
