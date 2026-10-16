const paths = {
  play: 'm8 5 11 7-11 7Z',
  pause: 'M8 5v14M16 5v14',
  restart: 'M4 10a8 8 0 1 1 1 8M4 4v6h6',
  previous: 'M5 5v14m14-14-10 7 10 7Z',
  next: 'M19 5v14M5 5l10 7-10 7Z',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  court: 'm8 3 8 8m-5-9 6 6-6 6-6-6Zm-1 9-7 7m9 2h9',
  ball: 'm12 8 4 3-2 5h-4l-2-5Z',
}

export default function BroadcastIcon({ name, size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {name === 'ball' ? <circle cx="12" cy="12" r="10" /> : null}
      <path d={paths[name] || paths.arrow} />
    </svg>
  )
}
