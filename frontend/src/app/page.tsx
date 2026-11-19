import Image from "next/image";
import Chat from "../components/Chat";

export default function Home() {
  return (
    <main className="app">
      <header className="topbar">
        <Image className="brand" src="/darglobal-logo.jpg" alt="DarGlobal" width={160} height={80} priority />
        <span className="header-title">AI Property Assistant</span>
      </header>
      <div className="workspace">
        <aside className="hero" aria-label="Discover DarGlobal">
          <div className="hero-copy">
            <h1>Find your<br /> next address.</h1>
            <p>Explore DarGlobal developments and discover homes listed on Wasalt.</p>
          </div>
        </aside>
        <Chat />
      </div>
    </main>
  );
}
