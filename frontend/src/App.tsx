import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Account } from "./pages/Account";
import { ChallengeList, ChallengePlay } from "./pages/Challenge";
import { Mastery } from "./pages/Mastery";
import { Glossary } from "./pages/Glossary";
import { Handbook } from "./pages/Handbook";
import { Home } from "./pages/Home";
import { Leaderboard } from "./pages/Leaderboard";
import { Lesson } from "./pages/Lesson";
import { Paths } from "./pages/Paths";
import { Planner } from "./pages/Planner";
import { Start } from "./pages/Start";

export default function App() {
  const { ready } = useAuth();
  if (!ready) return <p className="muted" style={{ padding: 24 }}>Loading Blueprint School...</p>;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/lesson/:id" element={<Lesson />} />
        <Route path="/start" element={<Start />} />
        <Route path="/paths" element={<Paths />} />
        <Route path="/challenge" element={<ChallengeList />} />
        <Route path="/challenge/:id" element={<ChallengePlay />} />
        <Route path="/mastery" element={<Mastery />} />
        <Route path="/glossary" element={<Glossary />} />
        <Route path="/planner" element={<Planner />} />
        <Route path="/handbook" element={<Handbook />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/account" element={<Account />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
