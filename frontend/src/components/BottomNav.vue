<template>
  <nav class="bottom-nav">
    <RouterLink to="/" class="nav-item"><span class="icon">🏠</span>ホーム</RouterLink>
    <RouterLink to="/transactions" class="nav-item"><span class="icon">📄</span>履歴</RouterLink>
    <RouterLink to="/transactions/new" class="fab" aria-label="取引を追加">＋</RouterLink>
    <RouterLink to="/recurring" class="nav-item"><span class="icon">🔁</span>固定費</RouterLink>
    <RouterLink to="/settings" class="nav-item"><span class="icon">⚙️</span>設定</RouterLink>
  </nav>
</template>

<style scoped>
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: calc(var(--nav-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: #fff;
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  max-width: 640px;
  margin: 0 auto;
  z-index: 10;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 0.7rem;
  color: var(--color-text-sub);
  text-decoration: none;
  min-width: 44px;
}

.nav-item.router-link-active {
  color: var(--color-primary);
  font-weight: 700;
}

.icon {
  font-size: 1.3rem;
  line-height: 1;
}

.fab {
  align-self: center;
  width: 52px;
  height: 52px;
  margin-top: -20px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  font-size: 1.8rem;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  flex-shrink: 0;
}
</style>
