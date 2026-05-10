"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Network } from "lucide-react";

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="navbar-logo">LogosForge</span>
      </div>
      <div className="navbar-links">
        <Link href="/" className={pathname === "/" ? "active" : ""}>
          <BookOpen size={16} />
          工作台
        </Link>
        <Link href="/graph" className={pathname === "/graph" ? "active" : ""}>
          <Network size={16} />
          知识图谱
        </Link>
      </div>
    </nav>
  );
}
