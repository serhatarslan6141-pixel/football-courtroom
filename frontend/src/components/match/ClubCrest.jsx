export default function ClubCrest({ club, small = false }) {
  return (
    <span
      className={`club-crest${small ? ' club-crest-small' : ''}`}
      style={{
        '--club-color': club.color,
        '--club-secondary': club.secondaryColor,
      }}
      aria-hidden="true"
    >
      <span>{club.shortName}</span>
    </span>
  )
}
