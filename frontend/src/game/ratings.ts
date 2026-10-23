import type { XI } from './types';

export const ratingColor = (rating: number) => rating >= 90 ? 'text-rating-red' : rating >= 80 ? 'text-rating-gold' : 'text-cream';

// Average only selected players; unfilled positions must not lower the rating.
export const squadValue = (xi: XI) => {
  const players = Object.values(xi).filter(player => player !== undefined && player !== null);
  return players.length ? Math.round(players.reduce((total, player) => total + player.rating, 0) / players.length * 10) / 10 : null;
};
