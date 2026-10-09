import { createRouter, createWebHashHistory } from 'vue-router';
import DashboardPage from '@/pages/DashboardPage.vue';
import StrategiesPage from '@/pages/StrategiesPage.vue';
import BacktestPage from '@/pages/BacktestPage.vue';
import OptimizationPage from '@/pages/OptimizationPage.vue';
import StrategyReviewPage from '@/pages/StrategyReviewPage.vue';
import BotsPage from '@/pages/BotsPage.vue';
import RiskPage from '@/pages/RiskPage.vue';
import MarketIntelPage from '@/pages/MarketIntelPage.vue';
import LogsPage from '@/pages/LogsPage.vue';
import SettingsPage from '@/pages/SettingsPage.vue';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: DashboardPage,
      meta: { title: '系統總覽' }
    },
    {
      path: '/strategies',
      name: 'strategies',
      component: StrategiesPage,
      meta: { title: '策略中心' }
    },
    {
      path: '/backtest',
      name: 'backtest',
      component: BacktestPage,
      meta: { title: '歷史回測' }
    },
    {
      path: '/optimization',
      name: 'optimization',
      component: OptimizationPage,
      meta: { title: '參數優化' }
    },
    {
      path: '/review',
      name: 'review',
      component: StrategyReviewPage,
      meta: { title: '策略覆盤' }
    },
    {
      path: '/bots',
      name: 'bots',
      component: BotsPage,
      meta: { title: '機器人管理' }
    },
    {
      path: '/risk',
      name: 'risk',
      component: RiskPage,
      meta: { title: '風控中心' }
    },
    {
      path: '/market-intel',
      name: 'market-intel',
      component: MarketIntelPage,
      meta: { title: '市場情報' }
    },
    {
      path: '/logs',
      name: 'logs',
      component: LogsPage,
      meta: { title: '系統日誌' }
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsPage,
      meta: { title: '系統設定' }
    }
  ]
});

// Guard ensuring navigation never triggers control commands
router.afterEach((to) => {
  if (to.meta?.title) {
    document.title = `catOS · ${to.meta.title}`;
  }
});

export default router;
