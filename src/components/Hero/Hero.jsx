import React from 'react';
import styles from './Hero.module.css';

const Hero = () => {
  return (
    <header className={styles.hero}>
      <div className={styles.heroOverlay}></div>
      <nav className={styles.heroNav}>
        <img src="/Gotor Comunicaciones Blanco.png" alt="Gotor Comunicaciones" className={styles.heroLogo} />
      </nav>
      <div className={styles.heroContent}>
        <h1 className={styles.heroTitle}>
          CALCULADORA<br /><span>AWS</span>
        </h1>
        <p className={styles.heroSubtitle}>
          Bienvenido a la calculadora automática de metros de cableado para los datacenter de Amazon
        </p>
      </div>
    </header>
  );
};

export default Hero;
