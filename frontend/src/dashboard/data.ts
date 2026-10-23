export type Period = '7d' | '30d' | '90d';

export interface TrendPoint {
  label: string;
  registrations: number;
  activePlayers: number;
}

export interface Segment {
  label: string;
  value: number;
  color: string;
}

export interface PopularSquad {
  name: string;
  tournament: string;
  share: number;
}

export interface DashboardSnapshot {
  period: Period;
  periodLabel: string;
  totalRegistered: number;
  newRegistrations: number;
  activePlayers: number;
  sessions: number;
  engagedSessions: number;
  draftStarts: number;
  matchesFinished: number;
  resultsCopied: number;
  averageSessionSeconds: number;
  trend: TrendPoint[];
  acquisition: Segment[];
  devices: Segment[];
}

const colors = {
  amber: '#f5a623',
  sky: '#83a9c7',
  mint: '#7bbba0',
  lavender: '#a6a1cf',
  slate: '#64717d',
};

const snapshots: Record<Period, DashboardSnapshot> = {
  '7d': {
    period: '7d', periodLabel: 'Last 7 days', totalRegistered: 12480,
    newRegistrations: 734, activePlayers: 2984, sessions: 6380,
    engagedSessions: 4252, draftStarts: 3810, matchesFinished: 2764,
    resultsCopied: 912, averageSessionSeconds: 522,
    trend: [
      { label: 'Mon', registrations: 88, activePlayers: 1180 },
      { label: 'Tue', registrations: 94, activePlayers: 1260 },
      { label: 'Wed', registrations: 107, activePlayers: 1320 },
      { label: 'Thu', registrations: 95, activePlayers: 1250 },
      { label: 'Fri', registrations: 116, activePlayers: 1420 },
      { label: 'Sat', registrations: 123, activePlayers: 1510 },
      { label: 'Sun', registrations: 111, activePlayers: 1490 },
    ],
    acquisition: [
      { label: 'Direct', value: 41, color: colors.amber },
      { label: 'Search', value: 25, color: colors.sky },
      { label: 'Social', value: 17, color: colors.mint },
      { label: 'Referral', value: 10, color: colors.lavender },
      { label: 'Other', value: 7, color: colors.slate },
    ],
    devices: [
      { label: 'Mobile', value: 64, color: colors.amber },
      { label: 'Desktop', value: 29, color: colors.sky },
      { label: 'Tablet', value: 7, color: colors.slate },
    ],
  },
  '30d': {
    period: '30d', periodLabel: 'Last 30 days', totalRegistered: 12480,
    newRegistrations: 2860, activePlayers: 6450, sessions: 25700,
    engagedSessions: 16936, draftStarts: 14980, matchesFinished: 10984,
    resultsCopied: 3860, averageSessionSeconds: 508,
    trend: [
      { label: '1–5', registrations: 390, activePlayers: 2540 },
      { label: '6–10', registrations: 426, activePlayers: 2720 },
      { label: '11–15', registrations: 448, activePlayers: 2900 },
      { label: '16–20', registrations: 474, activePlayers: 3050 },
      { label: '21–25', registrations: 526, activePlayers: 3290 },
      { label: '26–30', registrations: 596, activePlayers: 3510 },
    ],
    acquisition: [
      { label: 'Direct', value: 38, color: colors.amber },
      { label: 'Search', value: 27, color: colors.sky },
      { label: 'Social', value: 18, color: colors.mint },
      { label: 'Referral', value: 11, color: colors.lavender },
      { label: 'Other', value: 6, color: colors.slate },
    ],
    devices: [
      { label: 'Mobile', value: 62, color: colors.amber },
      { label: 'Desktop', value: 30, color: colors.sky },
      { label: 'Tablet', value: 8, color: colors.slate },
    ],
  },
  '90d': {
    period: '90d', periodLabel: 'Last 90 days', totalRegistered: 12480,
    newRegistrations: 8220, activePlayers: 9790, sessions: 71300,
    engagedSessions: 45800, draftStarts: 41400, matchesFinished: 29700,
    resultsCopied: 10540, averageSessionSeconds: 491,
    trend: [
      { label: 'W1', registrations: 550, activePlayers: 1840 },
      { label: 'W2', registrations: 580, activePlayers: 2100 },
      { label: 'W3', registrations: 612, activePlayers: 2280 },
      { label: 'W4', registrations: 630, activePlayers: 2540 },
      { label: 'W5', registrations: 648, activePlayers: 2730 },
      { label: 'W6', registrations: 667, activePlayers: 2950 },
      { label: 'W7', registrations: 680, activePlayers: 3120 },
      { label: 'W8', registrations: 701, activePlayers: 3350 },
      { label: 'W9', registrations: 720, activePlayers: 3480 },
      { label: 'W10', registrations: 745, activePlayers: 3670 },
      { label: 'W11', registrations: 812, activePlayers: 3900 },
      { label: 'W12', registrations: 875, activePlayers: 4200 },
    ],
    acquisition: [
      { label: 'Direct', value: 35, color: colors.amber },
      { label: 'Search', value: 29, color: colors.sky },
      { label: 'Social', value: 18, color: colors.mint },
      { label: 'Referral', value: 12, color: colors.lavender },
      { label: 'Other', value: 6, color: colors.slate },
    ],
    devices: [
      { label: 'Mobile', value: 60, color: colors.amber },
      { label: 'Desktop', value: 31, color: colors.sky },
      { label: 'Tablet', value: 9, color: colors.slate },
    ],
  },
};

export const getSnapshot = (period: Period): DashboardSnapshot => snapshots[period];

export const popularSquadsByPeriod: Record<Period, PopularSquad[]> = {
  '7d': [
    { name: 'India', tournament: 'World Cup 2011', share: 27 },
    { name: 'Australia', tournament: 'World Cup 2003', share: 20 },
    { name: 'England', tournament: 'World Cup 2019', share: 15 },
    { name: 'West Indies', tournament: 'World Cup 1979', share: 12 },
    { name: 'Pakistan', tournament: 'World Cup 1992', share: 9 },
  ],
  '30d': [
    { name: 'India', tournament: 'World Cup 2011', share: 24 },
    { name: 'Australia', tournament: 'World Cup 2003', share: 19 },
    { name: 'England', tournament: 'World Cup 2019', share: 16 },
    { name: 'West Indies', tournament: 'World Cup 1979', share: 13 },
    { name: 'Pakistan', tournament: 'World Cup 1992', share: 10 },
  ],
  '90d': [
    { name: 'India', tournament: 'World Cup 2011', share: 22 },
    { name: 'Australia', tournament: 'World Cup 2003', share: 18 },
    { name: 'England', tournament: 'World Cup 2019', share: 17 },
    { name: 'West Indies', tournament: 'World Cup 1979', share: 14 },
    { name: 'Pakistan', tournament: 'World Cup 1992', share: 11 },
  ],
};

export const formatNumber = (value: number): string => new Intl.NumberFormat('en-IN').format(value);

export const formatCompact = (value: number): string => value >= 1000 ? `${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k` : String(value);

export const percent = (part: number, whole: number): string => `${((part / whole) * 100).toFixed(1)}%`;

export const formatDuration = (seconds: number): string => `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`;
