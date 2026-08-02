import { Link, Route, Routes } from "react-router-dom";
import { getCurrentUserClaims } from "./api/client";
import AdminCells from "./routes/AdminCells";
import ApprovalInbox from "./routes/ApprovalInbox";
import DigestView from "./routes/DigestView";
import Login from "./routes/Login";
import MailboxConnect from "./routes/MailboxConnect";
import OrgMembers from "./routes/OrgMembers";
import SkillSettings from "./routes/SkillSettings";

export default function App() {
  const claims = getCurrentUserClaims();
  const isOrgAdmin = claims?.role === "org_admin" || claims?.role === "platform_admin";
  const isPlatformAdmin = claims?.role === "platform_admin";

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <Link to="/">Approval Inbox</Link>
        <Link to="/mailboxes">Mailboxes</Link>
        <Link to="/digests">Digests</Link>
        {isOrgAdmin && <Link to="/skill-settings">Skill Settings</Link>}
        {isOrgAdmin && <Link to="/members">Members</Link>}
        {isPlatformAdmin && <Link to="/admin/cells">Cells (admin)</Link>}
        <Link to="/login">Login</Link>
      </nav>
      <Routes>
        <Route path="/" element={<ApprovalInbox />} />
        <Route path="/mailboxes" element={<MailboxConnect />} />
        <Route path="/digests" element={<DigestView />} />
        <Route path="/skill-settings" element={<SkillSettings />} />
        <Route path="/members" element={<OrgMembers />} />
        <Route path="/admin/cells" element={<AdminCells />} />
        <Route path="/login" element={<Login />} />
      </Routes>
    </div>
  );
}
