import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0c10',
        'bg-raised': '#0e1116',
        ink: '#eef0f3',
        'ink-dim': '#9aa3ad',
        'ink-faint': '#626b74',
        line: 'rgba(238, 240, 243, 0.14)',
        accent: '#d7ff3d',
        safe: '#59d68b',
        danger: '#ff6a5e',
        warn: '#e8b64a',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['Inter', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        sm: '3px',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
