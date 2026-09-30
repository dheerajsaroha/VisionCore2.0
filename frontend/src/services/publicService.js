import { apiClient } from './apiClient';

/**
 * Public plan catalog for the marketing pricing page.
 *
 * The endpoint is unauthenticated and read-only, returning only plan names,
 * prices, trial lengths, feature codes and capacity limits. Feature gating is
 * enforced server-side, so the values shown here are the same limits the
 * backend applies to the tenant's requests.
 */
export const getPublicPlans = async () => {
  const response = await apiClient.get('/public/plans');
  return response.data;
};

export default { getPublicPlans };
