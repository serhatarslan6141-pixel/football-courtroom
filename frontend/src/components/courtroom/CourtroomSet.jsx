export function CourtSeal({ className = 'court-seal' }) {
  return (
    <svg
      className={className}
      viewBox="0 0 80 80"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="40"
        cy="40"
        r="36"
        stroke="currentColor"
        strokeOpacity=".35"
      />
      <circle
        cx="40"
        cy="40"
        r="30"
        stroke="currentColor"
        strokeOpacity=".15"
      />
      <path
        d="M40 19v38m-13 4h26M22 31h36M40 24l-18 7m18-7 18 7M22 31l-8 17h16l-8-17Zm36 0-8 17h16l-8-17Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M14 48a8 7 0 0 0 16 0m20 0a8 7 0 0 0 16 0"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  )
}

export default function CourtroomSet() {
  return (
    <svg
      className="courtroom-set"
      viewBox="0 0 1400 720"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="court-wall" x2="0" y2="1">
          <stop stopColor="#201d2d" />
          <stop offset="1" stopColor="#0c0e16" />
        </linearGradient>
        <linearGradient id="court-floor" x2="0" y2="1">
          <stop stopColor="#30262b" />
          <stop offset="1" stopColor="#0d0d16" />
        </linearGradient>
        <linearGradient id="court-column">
          <stop stopColor="#15151f" />
          <stop offset=".5" stopColor="#38303e" />
          <stop offset="1" stopColor="#14141e" />
        </linearGradient>
      </defs>
      <rect width="1400" height="720" fill="url(#court-wall)" />
      <path d="M0 490 700 440 1400 490V720H0Z" fill="url(#court-floor)" />
      <g stroke="#aa8b6550" fill="#0f101a">
        <path d="M88 60h240v385H88Zm984 0h240v385h-240Z" />
        <path d="M105 78h206v345H105Zm984 0h206v345h-206Z" opacity=".4" />
        <path d="M388 18h624v261H388Z" fill="#201b2c" />
        <path d="M405 35h590v227H405Z" opacity=".35" />
      </g>
      <g fill="url(#court-column)" stroke="#77614c50">
        {[45, 337, 1025, 1317].map((x) => (
          <g key={x}>
            <path d={`M${x} 25h38v438h-38Z`} />
            <path d={`M${x - 7} 25h52v13h-52Zm0 425h52v15h-52Z`} />
          </g>
        ))}
      </g>
      <g stroke="#bc98611a" fill="none">
        <path d="M0 490 700 440 1400 490M0 550h1400M0 625h1400" />
        {[0, 200, 400, 600, 800, 1000, 1200, 1400].map((x) => (
          <path key={x} d={`M${700 + (x - 700) * 0.3} 465 ${x} 720`} />
        ))}
      </g>
      <g fill="#c6a76d" opacity=".45">
        <rect x="121" y="125" width="2" height="110" />
        <rect x="1277" y="125" width="2" height="110" />
      </g>
    </svg>
  )
}
