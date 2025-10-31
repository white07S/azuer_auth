import {
  HomePage,
  DocsPage,
  ChatPage,
  ScenarioGeneratorPage,
  ScenarioLibraryPage,
  DashboardPage,
  GlossaryPage,
  TaskPage,
  OneOffFeaturePage,
  FeedbackPage,
  UnauthorizedPage,
} from '../pages';

export const NAVIGATION_ITEMS = [
  { key: 'home', label: 'Home', path: '/', component: HomePage, roles: ['user', 'admin'], requiresAuth: true },
  { key: 'docs', label: 'Docs', path: '/docs', component: DocsPage, roles: ['user', 'admin'], requiresAuth: true },
  { key: 'chat', label: 'Chat', path: '/chat', component: ChatPage, roles: ['admin'], requiresAuth: true },
  { key: 'scenario-generator', label: 'Scenario Generator', path: '/scenario/generator', component: ScenarioGeneratorPage, roles: ['admin'], requiresAuth: true },
  { key: 'scenario-library', label: 'Scenario Library', path: '/scenario/library', component: ScenarioLibraryPage, roles: ['admin'], requiresAuth: true },
  { key: 'dashboard', label: 'Dashboard', path: '/dashboard', component: DashboardPage, roles: ['admin'], requiresAuth: true },
  { key: 'glossary', label: 'Glossary', path: '/glossary', component: GlossaryPage, roles: ['user', 'admin'], requiresAuth: true },
  { key: 'task', label: 'Task', path: '/task', component: TaskPage, roles: ['admin'], requiresAuth: true },
  { key: 'one-off-feature', label: 'OneOffFeature', path: '/one-off-feature', component: OneOffFeaturePage, roles: ['admin'], requiresAuth: true },
  { key: 'feedback', label: 'Feedback', path: '/feedback', component: FeedbackPage, roles: ['user', 'admin'], requiresAuth: true },
];

export const UNAUTHORIZED_ROUTE = {
  key: 'unauthorized',
  label: 'Unauthorized',
  path: '/unauthorized',
  component: UnauthorizedPage,
};
