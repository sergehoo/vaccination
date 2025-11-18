/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./inhp/templates/**/*.html",
    "./**/templates/**/*.html",
    "./static/js/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        ivoireBlue: '#1A57A1',
        ivoireGreen: '#18A999',
        ivoireOrange: '#F59E0B',
        ivoireNight: '#020617',
        keneyaPrimary: '#1A57A1',
        keneyaSecondary: '#18A999',
        keneyaAccent: '#F59E0B'
      },
      boxShadow: {
        soft: '0 18px 45px rgba(15,23,42,0.24)',
      },
      borderRadius: {
        '3xl': '1.75rem',
        '4xl': '2rem'
      }
    },
  },
  plugins: [],
}