import React from "react";
import "../styles/Landing.css"

/**
 * Rock Creek Curling - Landing page
 * Mobile-first. No required props.
 *
 * Props (all optional):
 *  logoSrc          path to the logo (default "/logo.png", provided alongside this file)
 *  onSignIn         called when "Sign in" is pressed
 *  onCreateAccount  called when "Create account" is pressed
 */


export default function Landing({
  logoSrc = "/logo.png",
  onSignIn = () => {},
  onCreateAccount = () => {},
}) {
  return (
    <div className="rcc">
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


        <footer className="rcc-foot">
          <b>Rock Creek Curling</b>
          Lafayette, CO
        </footer>
      </div>
    </div>
  );
}
