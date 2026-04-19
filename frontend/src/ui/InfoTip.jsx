import { useState } from "react";

export default function InfoTip({ label, text }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span className={`info-tip ${isOpen ? "open" : ""}`} onMouseLeave={() => setIsOpen(false)}>
      <button
        type="button"
        className="info-tip-trigger"
        aria-label={`About ${label}`}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        ?
      </button>
      <span className="info-tip-bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}
