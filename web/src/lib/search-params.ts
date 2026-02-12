import {
	parseAsString,
	createSearchParamsCache,
} from "nuqs/server";

export const searchParamsParsers = {
	season: parseAsString,
	division: parseAsString,
};

export const searchParamsCache = createSearchParamsCache(searchParamsParsers);
