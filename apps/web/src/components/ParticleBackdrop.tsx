import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  alpha: number;
};

type CanvasSize = {
  width: number;
  height: number;
};

export const PARTICLE_SETTINGS = {
  disabledBelowWidth: 768,
  minParticles: 30,
  maxParticles: 75,
  density: 9500,
  colors: ["40, 54, 24", "221, 161, 94", "51, 65, 85"],
  minSize: 1.5,
  maxSize: 4.2,
  minOpacity: 0.2,
  maxOpacity: 0.3,
  speed: 0.1,
  linkDistance: 145,
  linkColor: "15, 118, 110",
  linkOpacity: 0.15,
};

export function ParticleBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = window.matchMedia(
      `(max-width: ${PARTICLE_SETTINGS.disabledBelowWidth - 1}px)`,
    ).matches;

    if (!canvas || !context || prefersReducedMotion || isMobile) return undefined;

    let animationFrame = 0;
    let particles: Particle[] = [];

    let canvasSize: CanvasSize = {
      width: 0,
      height: 0,
    };

    const getParticleCount = ({ width, height }: CanvasSize) =>
      Math.min(
        PARTICLE_SETTINGS.maxParticles,
        Math.max(
          PARTICLE_SETTINGS.minParticles,
          Math.floor((width * height) / PARTICLE_SETTINGS.density),
        ),
      );

    const createParticle = (size: CanvasSize, index: number): Particle => ({
      x: Math.random() * size.width,
      y: Math.random() * size.height,
      vx: (Math.random() - 0.5) * PARTICLE_SETTINGS.speed,
      vy: (Math.random() - 0.5) * PARTICLE_SETTINGS.speed,
      size:
        PARTICLE_SETTINGS.minSize +
        Math.random() * (PARTICLE_SETTINGS.maxSize - PARTICLE_SETTINGS.minSize),
      color: PARTICLE_SETTINGS.colors[index % PARTICLE_SETTINGS.colors.length],
      alpha:
        PARTICLE_SETTINGS.minOpacity +
        Math.random() * (PARTICLE_SETTINGS.maxOpacity - PARTICLE_SETTINGS.minOpacity),
    });

    const buildParticles = (size: CanvasSize) => {
      const count = Math.min(
        PARTICLE_SETTINGS.maxParticles,
        Math.max(
          PARTICLE_SETTINGS.minParticles,
          Math.floor((size.width * size.height) / PARTICLE_SETTINGS.density),
        ),
      );

      particles = Array.from({ length: count }, (_, index) => createParticle(size, index));
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      const nextSize = {
        width: Math.max(1, rect.width),
        height: Math.max(1, rect.height),
      };
      const previousSize = canvasSize;

      canvas.width = Math.max(1, Math.floor(rect.width * pixelRatio));
      canvas.height = Math.max(1, Math.floor(rect.height * pixelRatio));
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      canvasSize = nextSize;

      if (particles.length === 0 || previousSize.width === 0 || previousSize.height === 0) {
        buildParticles(nextSize);
        return;
      }

      const scaleX = nextSize.width / previousSize.width;
      const scaleY = nextSize.height / previousSize.height;

      particles = particles.map((particle) => ({
        ...particle,
        x: Math.min(nextSize.width + 8, Math.max(-8, particle.x * scaleX)),
        y: Math.min(nextSize.height + 8, Math.max(-8, particle.y * scaleY)),
      }));

      const targetCount = getParticleCount(nextSize);

      if (particles.length < targetCount) {
        const missingCount = targetCount - particles.length;
        particles = [
          ...particles,
          ...Array.from({ length: missingCount }, (_, index) =>
            createParticle(nextSize, particles.length + index),
          ),
        ];
      } else if (particles.length > targetCount) {
        particles = particles.slice(0, targetCount);
      }
    };

    const draw = () => {
      const rect = canvas.getBoundingClientRect();

      context.clearRect(0, 0, rect.width, rect.height);

      for (const particle of particles) {
        particle.x += particle.vx;
        particle.y += particle.vy;

        if (particle.x < -8) particle.x = rect.width + 8;
        if (particle.x > rect.width + 8) particle.x = -8;
        if (particle.y < -8) particle.y = rect.height + 8;
        if (particle.y > rect.height + 8) particle.y = -8;

        context.beginPath();
        context.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        context.fillStyle = `rgba(${particle.color}, ${particle.alpha})`;
        context.fill();
      }

      for (let i = 0; i < particles.length; i += 1) {
        for (let j = i + 1; j < particles.length; j += 1) {
          const first = particles[i];
          const second = particles[j];
          const dx = first.x - second.x;
          const dy = first.y - second.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance > PARTICLE_SETTINGS.linkDistance) continue;

          context.beginPath();
          context.moveTo(first.x, first.y);
          context.lineTo(second.x, second.y);
          context.strokeStyle = `rgba(${PARTICLE_SETTINGS.linkColor}, ${
            PARTICLE_SETTINGS.linkOpacity * (1 - distance / PARTICLE_SETTINGS.linkDistance)
          })`;
          context.lineWidth = 1;
          context.stroke();
        }
      }

      animationFrame = window.requestAnimationFrame(draw);
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    resize();
    draw();

    return () => {
      resizeObserver.disconnect();
      window.cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 top-0 z-0 hidden h-dvh w-full opacity-100 md:block"
    />
  );
}
