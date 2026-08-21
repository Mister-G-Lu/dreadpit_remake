import { Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell.jsx";
import Home from "./pages/Home.jsx";
import Enter from "./pages/Enter.jsx";
import Connect from "./pages/Connect.jsx";
import Forge from "./pages/Forge.jsx";
import Stack from "./pages/Stack.jsx";
import Ash from "./pages/Ash.jsx";
import Firing from "./pages/Firing.jsx";
import Vessel from "./pages/Vessel.jsx";
import Match from "./pages/Match.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<Home />} />
        <Route path="/enter" element={<Enter />} />
        <Route path="/connect" element={<Connect />} />
        <Route path="/forge" element={<Forge />} />
        <Route path="/stack" element={<Stack />} />
        <Route path="/ash" element={<Ash />} />
        <Route path="/firing" element={<Firing />} />
        <Route path="/vessel/:id" element={<Vessel />} />
        <Route path="/match/:id" element={<Match />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
