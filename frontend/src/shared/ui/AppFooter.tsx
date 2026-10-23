export function AppFooter() {
  return (
    <footer className="app-footer">
      <div className="app-footer-top">
        <div>
          <a href="/" className="app-brand" aria-label="Kash Engine home">
            <span className="app-brand-mark" aria-hidden="true">
              k.
            </span>
            <span>
              kash<span className="app-brand-light">engine</span>
            </span>
          </a>
          <p>A little less noise. A lot more context.</p>
        </div>
        <nav aria-label="Resources">
          <a href="/">About Kash Engine</a>
          <a href="/docs/">API documentation</a>
          <a href="/legal/#terms">Terms</a>
          <a href="/legal/#privacy">Privacy</a>
        </nav>
      </div>
      <div className="app-footer-bottom">
        <p>
          Not financial advice. Predictions can be wrong. GMP is unofficial. Always do your own
          research.
        </p>
        <small>&copy; {new Date().getFullYear()} Kash Engine</small>
      </div>
    </footer>
  );
}
