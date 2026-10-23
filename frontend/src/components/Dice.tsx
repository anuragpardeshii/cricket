const faces = [[5], [1, 9], [1, 5, 9], [1, 3, 7, 9], [1, 3, 5, 7, 9], [1, 3, 4, 6, 7, 9]];

export function Dice({ rolling = false }: { rolling?: boolean }) {
  return <span className={`dice-stage ${rolling ? 'dice-rolling' : ''}`} aria-hidden="true">
    <span className="dice-shadow"/>
    <span className="dice-cube">{faces.map((pips, index) => <span key={index} className={`dice-face dice-face-${index + 1}`}>
      {pips.map(pip => <i key={pip} className="dice-pip" style={{ gridRow: Math.ceil(pip / 3), gridColumn: ((pip - 1) % 3) + 1 }}/>) }
    </span>)}</span>
  </span>;
}
