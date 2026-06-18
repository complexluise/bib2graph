/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      /* Design tokens — Dirección D-2 "Observatorio" */
      colors: {
        /* Base: fondos y superficies */
        obs: {
          bg:        "#0d0f14", /* fondo principal: casi negro azulado */
          surface:   "#151820", /* cards/paneles: ligeramente más claro */
          border:    "#252934", /* bordes y separadores */
          overlay:   "#1c2028", /* hover states, tooltips */
        },
        /* Texto: escala de luminosidad calibrada */
        text: {
          primary:   "#e8eaf0", /* texto principal: blanco cálido */
          secondary: "#8b92a8", /* labels, metadata */
          muted:     "#4a5068", /* placeholders, disabled */
          accent:    "#c5cfe8", /* énfasis suave */
        },
        /* Comunidades del grafo: paleta protagonista (saturada, distinguible) */
        community: {
          0:  "#4fc3f7", /* cyan */
          1:  "#a5d6a7", /* verde */
          2:  "#ffb74d", /* naranja */
          3:  "#ce93d8", /* violeta */
          4:  "#ef9a9a", /* rojo suave */
          5:  "#80cbc4", /* teal */
          6:  "#fff176", /* amarillo */
          7:  "#b0bec5", /* gris azulado */
        },
        /* Estado de curación */
        curation: {
          accepted:  "#4caf50",
          rejected:  "#f44336",
          candidate: "#607d8b",
          seed:      "#ffd54f",
        },
        /* Acción / interacción */
        action: {
          primary:   "#5c86e8", /* azul brillante para el grafo */
          hover:     "#7ba0f0",
          focus:     "#4169d4",
        },
      },
      fontFamily: {
        /* Tipografía "tool for thought": legible, técnica, cálida */
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      spacing: {
        /* Sistema de espaciado de 4px base */
        "col-left":  "240px",
        "col-right": "280px",
      },
      borderRadius: {
        obs: "6px",
      },
      boxShadow: {
        "obs-sm":  "0 1px 3px rgba(0,0,0,0.5)",
        "obs-md":  "0 4px 12px rgba(0,0,0,0.6)",
        "obs-glow": "0 0 20px rgba(92,134,232,0.15)",
      },
      animation: {
        "fade-in": "fadeIn 0.15s ease-in-out",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0", transform: "translateY(2px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
