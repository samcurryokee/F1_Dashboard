import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

export const getSessions = async () => {
  const res = await api.get("/sessions");
  return res.data;
};

export const getStandings = async (sessionId) => {
  const res = await api.get(`/sessions/${sessionId}/standings`);
  return res.data;
};

export const getDrivers = async (sessionId) => {
  const res = await api.get(`/sessions/${sessionId}/drivers`);
  return res.data;
};

export const getLaps = async (sessionId, driverNumber = null) => {
  const params = driverNumber ? { driver_number: driverNumber } : {};
  const res = await api.get(`/sessions/${sessionId}/laps`, { params });
  return res.data;
};

export const getNextRace = async () => {
  const res = await api.get("/next-race");
  return res.data;
};

export const getStandingsByOpenF1Key = async (sessionKey) => {
  const res = await api.get(`/sessions/by-key/${sessionKey}/standings`);
  return res.data;
};

export const getDriverChampionship = async (year = 2026) => {
  const res = await api.get("/standings/drivers", { params: { year } });
  return res.data;
};

export const getConstructorChampionship = async (year = 2026) => {
  const res = await api.get("/standings/constructors", { params: { year } });
  return res.data;
};

export const getLapsDetailed = async (sessionId) => {
  const res = await api.get(`/sessions/${sessionId}/laps-detailed`);
  return res.data;
};

export const getStints = async (sessionId) => {
  const res = await api.get(`/sessions/${sessionId}/stints`);
  return res.data;
};

export const getCurrentTyres = async (sessionId) => {
  const res = await api.get(`/sessions/${sessionId}/current-tyres`);
  return res.data;
};

export const getNextSession = async () => {
  const data = await getNextRace();
  return data.next_session;
};

export const getLastRace = async () => {
  const data = await getNextRace();
  return data.last_race;
};

export default api;