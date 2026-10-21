import ClubInsignia from './ClubInsignia.jsx'

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
      <ClubInsignia club={club} />
    </span>
  )
}
