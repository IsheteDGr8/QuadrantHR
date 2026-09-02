import heroImage from "../assets/hero.png";
import Button from "../components/ui/Button";

const FEATURES = [
  {
    title: "Draft & refine with AI",
    body: "Generate policy sections from a short questionnaire, then ask AI to explain or reword any passage in place.",
  },
  {
    title: "Sign-off, tracked",
    body: "Every employee's signature is recorded and searchable — see who's signed, who hasn't, and when.",
  },
  {
    title: "Incident Report Assistant",
    body: "Describe what happened, get matched to the relevant policy, and route it for human review in one flow.",
  },
  {
    title: "Delivered by role",
    body: "Policies route to the right audience automatically — HR, Managers, Engineers, and everyone else see only what applies to them.",
  },
];

// The very first screen — pitches the product and hands off to Login via
// onGetStarted. Kept separate from Login itself (see Login.jsx) so the
// pitch and the sign-in form aren't crammed into one screen.
function Landing({ onGetStarted }) {
  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-wordmark">Policy Guardian</div>
        <Button variant="secondary" size="sm" onClick={onGetStarted}>
          Sign in
        </Button>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <h1>Draft, sign, and track company policy — all in one place.</h1>
          <p className="landing-hero-lede">
            Policy Guardian helps HR write clearer policy faster, gets every employee's
            signature on record, and gives everyone a single place to ask questions about
            what applies to them.
          </p>
          <Button variant="primary" onClick={onGetStarted}>
            Get started
          </Button>
        </div>

        <img className="landing-hero-image" src={heroImage} alt="" />
      </section>

      <section className="landing-features">
        {FEATURES.map((f) => (
          <div className="landing-feature" key={f.title}>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

export default Landing;
