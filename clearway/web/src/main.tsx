import { createRoot } from "react-dom/client";
import "@fontsource-variable/schibsted-grotesk/wght.css";
import "@fontsource-variable/schibsted-grotesk/wght-italic.css";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./styles.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<App />);
