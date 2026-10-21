// Original vector identities. Club colors come from the existing match data;
// the shapes and symbols remain the same in fixtures, scoreboards and court.
const ink = '#14231e'
const paper = '#f3ecdc'

function Northbridge() {
  return <>
    <path d="M20 5h60l14 18-9 52-35 21-35-21L6 23Z" fill="var(--club-secondary)" />
    <path d="M23 10h54l12 15-8 47-31 19-31-19-8-47Z" fill="var(--club-color)" />
    <g fill="var(--club-secondary)">
      <path d="M22 28h17v38H22zm39 0h17v38H61zM19 22h7v10h-7zm13 0h7v10h-7zm29 0h7v10h-7zm13 0h7v10h-7z" />
      <path d="M32 42h36v9H32zm-13 21h62v8H19zM32 77h36v4H32z" />
    </g>
    <path d="M39 64V55a11 11 0 0 1 22 0v9Z" fill="var(--club-color)" />
    <path d="m50 18 3 5-3 5-3-5z" fill={paper} />
  </>
}

function Harbor() {
  return <>
    <circle cx="50" cy="50" r="46" fill="var(--club-color)" />
    <circle cx="50" cy="50" r="39" fill={ink} stroke="var(--club-secondary)" strokeWidth="2" />
    <g stroke="var(--club-color)" strokeWidth="3"><path d="M15 35h9m52 0h9M15 65h9m52 0h9" /></g>
    <g stroke="var(--club-secondary)" strokeWidth="6" strokeLinecap="round" fill="none">
      <circle cx="50" cy="29" r="7" /><path d="M50 36v35M36 44h28M26 56c0 20 24 15 24 23 0-8 24-3 24-23m-48 0-5 6m5-6 7 3m41-3 5 6m-5-6-7 3" />
    </g>
    <path d="M31 84q9-6 19 0 9 6 19 0" stroke="var(--club-color)" strokeWidth="3" fill="none" />
  </>
}

function Mossfield() {
  return <>
    <path d="m50 3 46 47-46 47L4 50Z" fill="var(--club-secondary)" />
    <path d="m50 10 39 40-39 40-39-40Z" fill="var(--club-color)" />
    <path d="M25 64h50M32 73h36M42 82h16" stroke={ink} strokeWidth="4" />
    <path d="M49 65V24m0 12c-15 1-18-7-15-13 10-1 16 4 15 13Zm1 9c17 0 22-8 18-15-10-2-18 5-18 15Zm-1 9c-18 0-23-9-18-16 11-1 18 6 18 16Zm1-19c13-2 14-9 10-14-8 1-11 7-10 14Z" fill="var(--club-secondary)" stroke="var(--club-secondary)" strokeWidth="3" strokeLinejoin="round" />
  </>
}

function Riverside() {
  return <>
    <path d="M15 12Q50-5 85 12v64L50 97 15 76Z" fill="var(--club-secondary)" />
    <path d="M21 16Q50 2 79 16v56L50 90 21 72Z" fill="var(--club-color)" />
    <path d="M28 24h44v8H28z" fill="var(--club-secondary)" />
    <path d="M24 46c16-15 36 15 52 0v9c-16 15-36-15-52 0Zm0 18c16-15 36 15 52 0v9c-16 15-36-15-52 0Z" fill="var(--club-secondary)" />
    <path d="m50 13 3 4-3 4-3-4Z" fill={paper} />
  </>
}

function Ashcombe() {
  return <>
    <path d="M50 3 89 26v48L50 97 11 74V26Z" fill="var(--club-secondary)" />
    <path d="m50 9 33 20v42L50 91 17 71V29Z" fill="var(--club-color)" />
    <circle cx="50" cy="50" r="29" fill="none" stroke="var(--club-secondary)" strokeWidth="2" />
    <path d="m50 16 9 25 22 9-22 9-9 25-9-25-22-9 22-9Z" fill="var(--club-secondary)" />
    <path d="m50 27 5 20-5 5-5-5Z" fill={ink} />
    <circle cx="50" cy="52" r="6" fill="var(--club-color)" />
  </>
}

function Briarhampton() {
  return <>
    <path d="m50 3 12 8 15 1 5 14 12 10-4 15 4 15-12 10-5 14-15 1-12 8-12-8-15-1-5-14L6 66l4-15-4-15 12-10 5-14 15-1Z" fill="var(--club-color)" />
    <circle cx="50" cy="51" r="36" fill="var(--club-secondary)" stroke={paper} strokeWidth="2" />
    <path d="M50 23c15 0 17 15 9 22 15-8 27 4 19 17-5 8-15 7-21 2 7 13-1 24-13 20-10-3-10-14-6-21-13 9-25 1-21-12 3-10 15-10 23-5-12-8-4-23 10-23Z" fill="var(--club-color)" />
    <path d="m50 36 5 10 11 1-8 8 2 11-10-5-10 5 2-11-8-8 11-1Z" fill={paper} />
    <circle cx="50" cy="51" r="6" fill="var(--club-secondary)" />
  </>
}

const identities = {
  'Northbridge City': ['northbridge-city', Northbridge],
  'Harbor Athletic': ['harbor-athletic', Harbor],
  'Mossfield United': ['mossfield-united', Mossfield],
  'Riverside Athletic': ['riverside-athletic', Riverside],
  'Ashcombe Rovers': ['ashcombe-rovers', Ashcombe],
  'Briarhampton FC': ['briarhampton-fc', Briarhampton],
}

export default function ClubInsignia({ club }) {
  const [identity, Insignia] = (Object.hasOwn(identities, club.name) ? identities[club.name] : null) || ['monogram', null]
  return <svg viewBox="0 0 100 100" fill="none" className="club-insignia" data-club-identity={identity} aria-hidden="true" focusable="false">
    {Insignia ? <Insignia /> : <><circle cx="50" cy="50" r="44" fill={ink} stroke="var(--club-color)" strokeWidth="6" /><text x="50" y="58" textAnchor="middle" fill={paper} fontSize="26" fontFamily="Georgia, serif">{club.shortName}</text></>}
  </svg>
}
