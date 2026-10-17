import React from "react";

/**
 * Rock Creek Curling - Landing page
 * Mobile-first. No required props.
 *
 * Props (all optional):
 *  logoSrc          path to the logo (default "/logo.png", provided alongside this file)
 *  onSignIn         called when "Sign in" is pressed
 *  onCreateAccount  called when "Create account" is pressed
 */

const GREEN = "#07683a";
const GOLD = "#b1a47d";
const INK = "#14301f";
const PAPER = "#f4f5f3";

const css = `
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap');
.rcc *{box-sizing:border-box;margin:0}
.rcc{font-family:Barlow,system-ui,sans-serif;font-weight:500;color:${INK};background:${PAPER};min-height:100vh;display:flex;justify-content:center}
.rcc-wrap{width:100%;max-width:430px;background:${PAPER}}
.rcc h1,.rcc h2,.rcc h3,.rcc .cond{font-family:'Barlow Condensed',sans-serif;text-transform:uppercase;letter-spacing:.04em}
.rcc-top{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:${GREEN};border-bottom:3px solid ${GOLD}}
.rcc-top img{height:52px;width:auto;display:block}
.rcc-btn{border:0;border-radius:10px;background:${GREEN};color:#fff;font:700 16px 'Barlow Condensed',sans-serif;letter-spacing:.08em;text-transform:uppercase;padding:14px 20px;cursor:pointer;width:100%}
.rcc-btn.gold{background:${GOLD};color:${GREEN}}
.rcc-btn.line{background:transparent;color:#fff;border:2px solid ${GOLD}}
.rcc-btn.sm{width:auto;padding:9px 16px;background:${GOLD};color:${GREEN}}
.rcc-hero{background:${GREEN};color:#fff;padding:30px 20px 34px;text-align:center}
.rcc-hero img{width:150px;height:auto;margin-bottom:16px}
.rcc-hero h1{font-size:40px;line-height:1}
.rcc-hero p{margin:12px auto 22px;max-width:300px;color:#e4ecdf;font-size:17px;line-height:1.4}
.rcc-hero .stack{display:flex;flex-direction:column;gap:10px}
.rcc-sec{padding:28px 20px 6px}
.rcc-sec h2{font-size:26px;margin-bottom:4px}
.rcc-sub{color:#5d695e;font-size:15px}
.rcc-card{display:flex;gap:14px;align-items:center;background:#fff;border:1px solid #dde1dc;border-radius:14px;padding:14px;margin-top:12px}
.rcc-card svg{flex:0 0 64px;width:64px;height:64px}
.rcc-card h3{font-size:19px;color:${GREEN}}
.rcc-card p{font-size:15px;color:#4d5a4e;line-height:1.35;margin-top:2px}
.rcc-steps{counter-reset:s;list-style:none;padding:0;margin-top:14px}
.rcc-steps li{counter-increment:s;display:flex;gap:14px;align-items:flex-start;padding:12px 0;border-top:1px solid #dde1dc}
.rcc-steps li:before{content:counter(s);flex:0 0 34px;height:34px;border-radius:50%;background:${GOLD};color:${GREEN};font:700 18px/34px 'Barlow Condensed',sans-serif;text-align:center}
.rcc-steps b{display:block;font:700 18px 'Barlow Condensed',sans-serif;text-transform:uppercase;letter-spacing:.04em}
.rcc-steps span{font-size:15px;color:#4d5a4e}
.rcc-cta{margin:26px 20px 0;padding:24px 18px;border-radius:16px;background:${INK};color:#fff;text-align:center}
.rcc-cta h2{font-size:28px;margin-bottom:14px}
.rcc-cta .stack{display:flex;flex-direction:column;gap:10px}
.rcc-foot{padding:26px 20px 34px;text-align:center;font-size:13px;color:#667066}
.rcc-foot b{display:block;font:700 15px 'Barlow Condensed',sans-serif;letter-spacing:.1em;text-transform:uppercase;color:${GREEN}}
`;

function House({ size = 64 }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <circle cx="50" cy="50" r="46" fill={GREEN} />
      <circle cx="50" cy="50" r="32" fill="#fff" />
      <circle cx="50" cy="50" r="19" fill={GOLD} />
      <circle cx="50" cy="50" r="6" fill="#fff" />
    </svg>
  );
}

function Calendar({ size = 64 }) {
  const cells = Array.from({ length: 15 }, (_, i) => i);
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <rect x="8" y="14" width="84" height="78" rx="10" fill="#fff" stroke={GREEN} strokeWidth="5" />
      <rect x="8" y="14" width="84" height="22" rx="10" fill={GREEN} />
      {cells.map((i) => (
        <rect
          key={i}
          x={18 + (i % 5) * 15}
          y={46 + Math.floor(i / 5) * 14}
          width="10"
          height="9"
          rx="2"
          fill={i === 7 ? GOLD : "#dde1dc"}
        />
      ))}
    </svg>
  );
}

function Stones({ size = 64 }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <circle cx="50" cy="50" r="46" fill={GREEN} />
      <circle cx="50" cy="50" r="30" fill="#fff" />
      <circle cx="42" cy="44" r="12" fill={INK} stroke="#fff" strokeWidth="3" />
      <circle cx="62" cy="60" r="12" fill="#d9b44a" stroke="#fff" strokeWidth="3" />
    </svg>
  );
}

const features = [
  {
    Icon: Stones,
    title: "Replay every shot",
    text: "Step through any game end by end and see exactly where each stone landed in the house.",
  },
  {
    Icon: House,
    title: "Your saved games",
    text: "Keep the games you care about in one place and jump back to them from your home page.",
  },
  {
    Icon: Calendar,
    title: "Find games by date",
    text: "Pick a date on the calendar to see the draws, sheets and leagues that played that night.",
  },
];

export default function Landing({
  logoSrc = "/logo.png",
  onSignIn = () => {},
  onCreateAccount = () => {},
}) {
  return (
    <div className="rcc">
      <style>{css}</style>
      <div className="rcc-wrap">
        <header className="rcc-top">
          <img src={logoSrc} alt="Rock Creek Curling" />
          <button className="rcc-btn sm" onClick={onSignIn}>
            Sign in
          </button>
        </header>

        <section className="rcc-hero">
          <img src={logoSrc} alt="" />
          <h1>Every shot, saved</h1>
          <p>
            Review your league games from Rock Creek Curling, end by end and
            stone by stone.
          </p>
          <div className="stack">
            <button className="rcc-btn gold" onClick={onCreateAccount}>
              Create account
            </button>
            <button className="rcc-btn line" onClick={onSignIn}>
              Sign in
            </button>
          </div>
        </section>

        <section className="rcc-sec">
          <h2>What you can do</h2>
          <p className="rcc-sub">Built for your phone, right from the sheet.</p>
          {features.map(({ Icon, title, text }) => (
            <div className="rcc-card" key={title}>
              <Icon />
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            </div>
          ))}
        </section>


        <footer className="rcc-foot">
          <b>Rock Creek Curling</b>
          Lafayette, CO
        </footer>
      </div>
    </div>
  );
}
