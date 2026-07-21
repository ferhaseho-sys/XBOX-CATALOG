import { useState, useCallback, useEffect } from 'react';
import { ProductDetails, RegionalPriceData, RegionalPrice, XboxMarket, MarketAnalysis } from '../types/scraper';

// Lista completa de mercados de Xbox (200+ regiones)
export const XBOX_MARKETS: XboxMarket[] = (() => {
  // Los 242 mercados de la Microsoft Store. Nombre de pais via Intl.DisplayNames,
  // bandera derivada del codigo. La moneda/precio la descubre la consulta EN VIVO.
  const CODES = [
  'US',
  'DZ',
  'AR',
  'AU',
  'AT',
  'BH',
  'BD',
  'BE',
  'BR',
  'BG',
  'CA',
  'CL',
  'CN',
  'CO',
  'CR',
  'HR',
  'CY',
  'CZ',
  'DK',
  'EG',
  'EE',
  'FI',
  'FR',
  'DE',
  'GR',
  'GT',
  'HK',
  'HU',
  'IS',
  'IN',
  'ID',
  'IQ',
  'IE',
  'IL',
  'IT',
  'JP',
  'JO',
  'KZ',
  'KE',
  'KW',
  'LV',
  'LB',
  'LI',
  'LT',
  'LU',
  'MY',
  'MT',
  'MR',
  'MX',
  'MA',
  'NL',
  'NZ',
  'NG',
  'NO',
  'OM',
  'PK',
  'PE',
  'PH',
  'PL',
  'PT',
  'QA',
  'RO',
  'RU',
  'SA',
  'RS',
  'SG',
  'SK',
  'SI',
  'ZA',
  'KR',
  'ES',
  'SE',
  'CH',
  'TW',
  'TH',
  'TT',
  'TN',
  'TR',
  'UA',
  'AE',
  'GB',
  'VN',
  'YE',
  'LY',
  'LK',
  'UY',
  'VE',
  'AF',
  'AX',
  'AL',
  'AS',
  'AO',
  'AI',
  'AQ',
  'AG',
  'AM',
  'AW',
  'BO',
  'BQ',
  'BA',
  'BW',
  'BV',
  'IO',
  'BN',
  'BF',
  'BI',
  'KH',
  'CM',
  'CV',
  'KY',
  'CF',
  'TD',
  'TL',
  'DJ',
  'DM',
  'DO',
  'EC',
  'SV',
  'GQ',
  'ER',
  'ET',
  'FK',
  'FO',
  'FJ',
  'GF',
  'PF',
  'TF',
  'GA',
  'GM',
  'GE',
  'GH',
  'GI',
  'GL',
  'GD',
  'GP',
  'GU',
  'GG',
  'GN',
  'GW',
  'GY',
  'HT',
  'HM',
  'HN',
  'AZ',
  'BS',
  'BB',
  'BY',
  'BZ',
  'BJ',
  'BM',
  'BT',
  'KM',
  'CG',
  'CD',
  'CK',
  'CX',
  'CC',
  'CI',
  'CW',
  'JM',
  'SJ',
  'JE',
  'KI',
  'KG',
  'LA',
  'LS',
  'LR',
  'MO',
  'MK',
  'MG',
  'MW',
  'IM',
  'MH',
  'MQ',
  'MU',
  'YT',
  'FM',
  'MD',
  'MN',
  'MS',
  'MZ',
  'MM',
  'NA',
  'NR',
  'NP',
  'MV',
  'ML',
  'NC',
  'NI',
  'NE',
  'NU',
  'NF',
  'PW',
  'PS',
  'PA',
  'PG',
  'PY',
  'RE',
  'RW',
  'BL',
  'MF',
  'WS',
  'ST',
  'SN',
  'MP',
  'PN',
  'SX',
  'SB',
  'SO',
  'SC',
  'SL',
  'GS',
  'SH',
  'KN',
  'LC',
  'PM',
  'VC',
  'TJ',
  'TZ',
  'TG',
  'TK',
  'TO',
  'TM',
  'TC',
  'TV',
  'UM',
  'UG',
  'VI',
  'VG',
  'WF',
  'EH',
  'ZM',
  'ZW',
  'UZ',
  'VU',
  'SR',
  'SZ',
  'AD',
  'MC',
  'SM',
  'ME',
  'VA'
  ];
  let names: any = null;
  try { names = new (Intl as any).DisplayNames(['es'], { type: 'region' }); } catch (e) {}
  const flagOf = (c: string) => (c && c.length === 2)
    ? String.fromCodePoint(...[...c.toUpperCase()].map(ch => 127397 + ch.charCodeAt(0))) : '';
  return CODES.map((code) => {
    let name = code;
    try { name = names?.of(code) || code; } catch (e) {}
    return { code, name, currency: '', locale: 'en-US', region: 'Global', flag: flagOf(code), active: true } as XboxMarket;
  });
})();

// Export aliases for backwards compatibility
export const ALL_REGIONS = XBOX_MARKETS;
export const FAVORITE_REGIONS = XBOX_MARKETS.filter(market => 
  ['US', 'GB', 'DE', 'FR', 'JP', 'AU', 'CA', 'BR', 'MX', 'AR'].includes(market.code)
);

// Tasas de cambio aproximadas (en producción usar API real)
const EXCHANGE_RATES: { [currency: string]: number } = {
  'USD': 1.0,
  'EUR': 0.85,
  'GBP': 0.73,
  'JPY': 110.0,
  'CAD': 1.25,
  'AUD': 1.35,
  'CHF': 0.92,
  'CNY': 6.45,
  'SEK': 8.65,
  'NOK': 8.95,
  'DKK': 6.35,
  'PLN': 3.85,
  'CZK': 21.5,
  'HUF': 295.0,
  'RON': 4.15,
  'BGN': 1.66,
  'HRK': 6.35,
  'RUB': 75.0,
  'TRY': 8.25,
  'KRW': 1180.0,
  'SGD': 1.35,
  'HKD': 7.75,
  'TWD': 28.0,
  'MYR': 4.15,
  'THB': 31.5,
  'PHP': 50.0,
  'IDR': 14250.0,
  'VND': 23000.0,
  'INR': 74.5,
  'AED': 3.67,
  'SAR': 3.75,
  'EGP': 15.7,
  'ZAR': 14.5,
  'ILS': 3.25,
  'NGN': 410.0,
  'KES': 108.0,
  'GHS': 6.1,
  'BRL': 5.2,
  'MXN': 20.1,
  'ARS': 98.5,
  'CLP': 750.0,
  'COP': 3650.0,
  'PEN': 3.95
};

interface APIError {
  message: string;
  status?: number;
  region?: string;
}

export const useXboxAPI = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  // Convertir precio a USD
  const convertToUSD = useCallback((price: number, currency: string): number => {
    const rate = EXCHANGE_RATES[currency] || 1;
    return price / rate;
  }, []);

  // Construir URL de la API de Xbox
  const buildXboxAPIUrl = useCallback((productId: string, market: XboxMarket): string => {
    const baseUrl = 'https://displaycatalog.mp.microsoft.com/v7.0/products';
    const hardware = 'arm0,arm640,ble1,cmb0,cmf0,cmr0,dcb0,dcc0,dx90,dxa0,dxb0,gyr0,hce0,hdc0,hov0,hsa0,hss1,kbd1,m040,m060,m080,m120,m160,m200,m300,m750,mA00,mct0,mgn0,mic0,mrc0,mse1,mT00,nfc0,rs10,rs20,rs30,rs40,rs50,rs60,tch0,tel0,v010,v020,v040,x641,x860,x86a640,xbd0,xbo0,xbs0,xbx0,xgp0';
    
    const params = new URLSearchParams({
      market: market.code,
      locale: market.locale,
      appVersion: '22407.1401.0.0',
      hardware: hardware,
      catalogLocales: `${market.locale},en-US`,
      idType: 'ProductId',
      deviceFamily: 'Windows.Desktop',
      preciseDeviceFamilyVersion: '2814751014981827',
      packageHardware: '',
      actionFilter: 'Details',
      cardsEnabled: 'true',
      languages: market.locale
    });

    return `${baseUrl}/${productId}?${params.toString()}`;
  }, []);

  // Extraer datos del producto desde la respuesta de la API
  const extractProductData = useCallback((apiResponse: any, market: XboxMarket): ProductDetails | null => {
    try {
      const product = apiResponse.Products?.[0];
      if (!product) return null;

      const displaySkuAvailabilities = product.DisplaySkuAvailabilities?.[0];
      const sku = displaySkuAvailabilities?.Sku;
      const availability = displaySkuAvailabilities?.Availabilities?.[0];
      const orderManagementData = availability?.OrderManagementData;
      const pricing = orderManagementData?.Price;

      // Extraer información de precios
      const listPrice = pricing?.ListPrice || 0;
      const msrp = pricing?.MSRP || listPrice;
      const wholeSalePrice = pricing?.WholesalePrice || listPrice;
      const currencyCode = pricing?.CurrencyCode || market.currency;

      // Extraer imágenes
      const localizedProperties = product.LocalizedProperties?.[0];
      const images = localizedProperties?.Images || [];
      const videos = localizedProperties?.Videos || [];

      // Extraer propiedades del producto
      const properties = product.Properties || {};
      const categories = properties.Category || [];
      const genres = properties.Genres || [];
      const platforms = properties.Platforms || [];

      return {
        productId: product.ProductId,
        title: localizedProperties?.ProductTitle || 'Unknown Title',
        description: localizedProperties?.ProductDescription || '',
        longDescription: localizedProperties?.ShortDescription || '',
        shortDescription: localizedProperties?.ShortTitle || '',
        category: categories[0] || 'Unknown',
        genres: genres,
        platforms: platforms,
        developer: properties.PublisherName || 'Unknown Developer',
        publisher: properties.PublisherName || 'Unknown Publisher',
        releaseDate: product.MarketProperties?.[0]?.OriginalReleaseDate || '',
        rating: parseFloat(product.MarketProperties?.[0]?.UsageData?.[0]?.AverageRating || '0'),
        ratingCount: parseInt(product.MarketProperties?.[0]?.UsageData?.[0]?.RatingCount || '0'),
        contentRating: properties.XboxLiveTier || 'Unknown',
        packageFamilyName: sku?.Properties?.PackageFamilyName || '',
        images: {
          icon: images.find((img: any) => img.ImagePurpose === 'Logo')?.Uri,
          hero: images.find((img: any) => img.ImagePurpose === 'FeaturePromotionalSquareArt')?.Uri,
          screenshots: images.filter((img: any) => img.ImagePurpose === 'Screenshot').map((img: any) => img.Uri),
          logos: images.filter((img: any) => img.ImagePurpose === 'Logo').map((img: any) => img.Uri),
          tiles: images.filter((img: any) => img.ImagePurpose === 'Tile').map((img: any) => img.Uri)
        },
        videos: {
          trailers: videos.filter((vid: any) => vid.VideoPurpose === 'Trailer').map((vid: any) => vid.Uri),
          gameplay: videos.filter((vid: any) => vid.VideoPurpose === 'Gameplay').map((vid: any) => vid.Uri)
        },
        features: properties.Features || [],
        requirements: {
          minimum: properties.MinimumSystemRequirements,
          recommended: properties.RecommendedSystemRequirements
        },
        fileSize: properties.PackageSize,
        languages: localizedProperties?.SupportedLanguages || [],
        accessibility: properties.AccessibilityFeatures || [],
        capabilities: properties.Capabilities || [],
        isGamePass: properties.XboxLiveTier === 'GamePass' || properties.IsGamePass === 'true',
        gamePassTier: properties.XboxLiveTier,
        dlcInfo: product.Children || [],
        bundleInfo: product.BundledSkus || []
      };
    } catch (error) {
      console.error('Error extracting product data:', error);
      return null;
    }
  }, []);

  // Obtener datos de precio regional
  const getRegionalPrice = useCallback(async (productId: string, market: XboxMarket): Promise<RegionalPrice | null> => {
    try {
      const url = buildXboxAPIUrl(productId, market);
      
      // Precios EN VIVO desde Microsoft (vía backend Atlas). UNA sola consulta trae
      // las 242 regiones (el backend hace la concurrencia); se cachea la promesa
      // por producto y cada mercado resuelve de ahí. Robusto (no 242 fetches).
      if (typeof window !== 'undefined' && !window.electronAPI) {
        const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';
        (window as any).__atlasLive = (window as any).__atlasLive || {};
        if (!(window as any).__atlasLive[productId]) {
          (window as any).__atlasLive[productId] = fetch(`${ATLAS_API}/api/live/product/${productId}`)
            .then((r) => (r.ok ? r.json() : { prices: [] }))
            .then((d) => d.prices || [])
            .catch(() => []);
        }
        const prices = await (window as any).__atlasLive[productId];
        const row = prices.find((r: any) => r.market === market.code);
        if (!row || row.list_price == null) return null;
        return {
          region: market.region,
          regionCode: market.code,
          countryName: market.name,
          currency: row.currency || market.currency,
          price: Number(row.list_price),
          originalPrice: Number(row.msrp ?? row.list_price),
          discount: Number(row.discount_pct || 0),
          priceUSD: Number(row.price_usd ?? convertToUSD(row.list_price, row.currency)),
          isFree: !!row.is_free,
          isOnSale: !!row.on_sale,
          dealUntil: row.sale_ends || undefined,
          lastUpdated: new Date().toISOString()
        };
      }

      // En Electron, hacer la llamada real a la API
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const product = data.Products?.[0];
      if (!product) return null;

      const displaySkuAvailabilities = product.DisplaySkuAvailabilities?.[0];
      const availability = displaySkuAvailabilities?.Availabilities?.[0];
      const pricing = availability?.OrderManagementData?.Price;

      if (!pricing) return null;

      const listPrice = pricing.ListPrice || 0;
      const msrp = pricing.MSRP || listPrice;
      const discount = msrp > 0 ? ((msrp - listPrice) / msrp) * 100 : 0;

      return {
        region: market.region,
        regionCode: market.code,
        countryName: market.name,
        currency: pricing.CurrencyCode || market.currency,
        price: listPrice,
        originalPrice: msrp,
        discount: Math.round(discount * 10) / 10,
        priceUSD: convertToUSD(listPrice, pricing.CurrencyCode || market.currency),
        isFree: listPrice === 0,
        isOnSale: discount > 0,
        dealUntil: availability?.Properties?.EndDate,
        lastUpdated: new Date().toISOString()
      };
    } catch (error) {
      console.error(`Error fetching price for ${market.name}:`, error);
      return null;
    }
  }, [buildXboxAPIUrl, convertToUSD]);

  // Obtener precios de todas las regiones para un producto
  const getRegionalPrices = useCallback(async (productId: string, selectedMarkets?: XboxMarket[]): Promise<RegionalPriceData | null> => {
    setLoading(true);
    setError(null);
    
    try {
      const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';
      const marketsToCheck = selectedMarkets || XBOX_MARKETS.filter(m => m.active);
      const marketByCode: Record<string, XboxMarket> = {};
      for (const m of marketsToCheck) marketByCode[m.code] = m;
      const codes = marketsToCheck.map(m => m.code).join(',');
      setProgress({ current: 0, total: marketsToCheck.length });

      // UNA sola llamada: el backend consulta Microsoft en vivo, concurrente.
      const resp = await fetch(`${ATLAS_API}/api/live/product/${productId}?markets=${codes}`);
      if (!resp.ok) throw new Error('No se pudo consultar el producto');
      const data = await resp.json();
      setProgress({ current: marketsToCheck.length, total: marketsToCheck.length });

      const validPrices: RegionalPrice[] = (data.prices || []).map((row: any) => {
        const m: any = marketByCode[row.market] || { region: 'Global', name: row.market };
        return {
          region: m.region, regionCode: row.market, countryName: m.name || row.market,
          currency: row.currency, price: Number(row.list_price),
          originalPrice: Number(row.msrp ?? row.list_price), discount: Number(row.discount_pct || 0),
          priceUSD: Number(row.price_usd ?? 0), isFree: !!row.is_free, isOnSale: !!row.on_sale,
          dealUntil: row.sale_ends || undefined, lastUpdated: new Date().toISOString()
        };
      });

      if (validPrices.length === 0) {
        throw new Error('No valid price data found for any region');
      }

      const lowestPrice = validPrices.reduce((min, p) => p.priceUSD < min.priceUSD ? p : min);
      const highestPrice = validPrices.reduce((max, p) => p.priceUSD > max.priceUSD ? p : max);
      const averagePrice = validPrices.reduce((sum, p) => sum + p.priceUSD, 0) / validPrices.length;
      const variance = validPrices.reduce((sum, p) => sum + Math.pow(p.priceUSD - averagePrice, 2), 0) / validPrices.length;

      return {
        productId,
        title: data.title || 'Unknown Product',
        regions: validPrices.sort((a, b) => a.priceUSD - b.priceUSD),
        lowestPrice,
        highestPrice,
        averagePrice: Math.round(averagePrice * 100) / 100,
        priceVariance: Math.round(variance * 100) / 100,
        totalRegions: validPrices.length,
        lastUpdated: new Date().toISOString(),
        variants: data.variants || []
      } as any;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
      setProgress({ current: 0, total: 0 });
    }
  }, []);

  // Analizar mercado para un producto
  const analyzeMarket = useCallback((regionalData: RegionalPriceData): MarketAnalysis => {
    const prices = regionalData.regions;
    const sortedPrices = [...prices].sort((a, b) => a.priceUSD - b.priceUSD);
    
    // Estadísticas globales
    const totalPrices = prices.length;
    const averagePrice = prices.reduce((sum, p) => sum + p.priceUSD, 0) / totalPrices;
    const medianPrice = sortedPrices[Math.floor(totalPrices / 2)].priceUSD;
    const lowestPrice = sortedPrices[0];
    const highestPrice = sortedPrices[totalPrices - 1];
    const priceSpread = highestPrice.priceUSD - lowestPrice.priceUSD;
    const coefficientOfVariation = (regionalData.priceVariance / averagePrice) * 100;

    // Categorías de precios
    const priceCategories = {
      free: prices.filter(p => p.isFree),
      veryLow: prices.filter(p => !p.isFree && p.priceUSD <= averagePrice * 0.5),
      low: prices.filter(p => p.priceUSD > averagePrice * 0.5 && p.priceUSD <= averagePrice * 0.8),
      medium: prices.filter(p => p.priceUSD > averagePrice * 0.8 && p.priceUSD <= averagePrice * 1.2),
      high: prices.filter(p => p.priceUSD > averagePrice * 1.2 && p.priceUSD <= averagePrice * 2),
      veryHigh: prices.filter(p => p.priceUSD > averagePrice * 2)
    };

    // Análisis de descuentos
    const discountedPrices = prices.filter(p => p.discount > 0);
    const bestDiscounts = discountedPrices.sort((a, b) => b.discount - a.discount).slice(0, 10);
    const noDiscounts = prices.filter(p => p.discount === 0);
    const averageDiscount = discountedPrices.length > 0 
      ? discountedPrices.reduce((sum, p) => sum + p.discount, 0) / discountedPrices.length 
      : 0;

    // Recomendaciones
    const bestValue = sortedPrices[0]; // Precio más bajo
    const bestForRegion: { [region: string]: RegionalPrice } = {};
    
    // Agrupar por región y encontrar el mejor precio en cada una
    const regionGroups = prices.reduce((groups, price) => {
      if (!groups[price.region]) {
        groups[price.region] = [];
      }
      groups[price.region].push(price);
      return groups;
    }, {} as { [region: string]: RegionalPrice[] });

    Object.keys(regionGroups).forEach(region => {
      const regionPrices = regionGroups[region];
      bestForRegion[region] = regionPrices.reduce((best, current) => 
        current.priceUSD < best.priceUSD ? current : best
      );
    });

    // Oportunidades de arbitraje (diferencias significativas de precio)
    const arbitrageOpportunities = [];
    for (let i = 0; i < Math.min(5, sortedPrices.length); i++) {
      for (let j = sortedPrices.length - 1; j >= Math.max(sortedPrices.length - 5, i + 1); j--) {
        const profit = sortedPrices[j].priceUSD - sortedPrices[i].priceUSD;
        if (profit > 10) { // Solo mostrar si la diferencia es > $10
          arbitrageOpportunities.push({
            buy: sortedPrices[i],
            sell: sortedPrices[j],
            profit: Math.round(profit * 100) / 100
          });
        }
      }
    }

    return {
      productId: regionalData.productId,
      title: regionalData.title,
      globalStats: {
        averagePrice: Math.round(averagePrice * 100) / 100,
        medianPrice: Math.round(medianPrice * 100) / 100,
        lowestPrice,
        highestPrice,
        priceSpread: Math.round(priceSpread * 100) / 100,
        coefficientOfVariation: Math.round(coefficientOfVariation * 100) / 100
      },
      regionalRanking: sortedPrices,
      priceCategories,
      discountAnalysis: {
        bestDiscounts,
        noDiscounts,
        averageDiscount: Math.round(averageDiscount * 100) / 100
      },
      recommendations: {
        bestValue,
        bestForRegion,
        arbitrageOpportunities: arbitrageOpportunities.slice(0, 10)
      }
    };
  }, []);

  // Buscar productos por término
  const searchProducts = useCallback(async (searchTerm: string, market: XboxMarket = XBOX_MARKETS[0]): Promise<ProductDetails[]> => {
    setLoading(true);
    setError(null);
    
    try {
      const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';
      const term = (searchTerm || '').trim();
      // Resolver a ProductIDs: si parece ID (12 chars) lo usamos directo; si no, buscamos por título.
      let ids: string[] = [];
      if (/^[0-9A-Za-z]{12}$/.test(term)) {
        ids = [term.toUpperCase()];
      } else if (term) {
        const found = await fetch(`${ATLAS_API}/api/search?term=${encodeURIComponent(term)}&limit=12`)
          .then(r => (r.ok ? r.json() : [])).catch(() => []);
        ids = (found as any[]).map(g => g.product_id);
      }
      const mkt = (market?.code || 'US');
      const details = await Promise.all(ids.slice(0, 12).map(async (id) => {
        const p = await fetch(`${ATLAS_API}/api/product/${id}?market=${mkt}`)
          .then(r => (r.ok ? r.json() : null)).catch(() => null);
        if (!p) return null;
        const priceRow = (p.prices || []).find((r: any) => r.market === mkt) || (p.prices || [])[0] || {};
        return {
          productId: p.product_id,
          title: p.title,
          description: p.description || p.short_desc || '',
          category: p.category || p.product_type || '',
          genres: p.categories || [],
          platforms: p.console_gen || ['Xbox'],
          developer: p.developer || '',
          publisher: p.publisher || '',
          releaseDate: p.release_date || '',
          rating: p.avg_rating || 0,
          ratingCount: p.rating_count || 0,
          contentRating: (p.ratings && (p.ratings.ESRB || p.ratings.PEGI)) || '',
          price: priceRow.list_price != null ? Number(priceRow.list_price) : undefined,
          priceUSD: priceRow.price_usd != null ? Number(priceRow.price_usd) : undefined,
          currency: priceRow.currency || '',
          images: { screenshots: [], logos: [], tiles: [], boxArt: p.image_boxart, hero: p.image_hero },
          imageUrl: p.image_boxart || p.image_hero || p.image_poster || '',
          trailer: p.trailer || '',
          features: [],
          requirements: {},
          languages: [],
          accessibility: [],
          capabilities: [],
          variants: p.variants || [],
          availableMarkets: p.n_available_markets || 0
        } as any;
      }));
      return details.filter(Boolean) as ProductDetails[];
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Search error occurred';
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    progress,
    getRegionalPrices,
    analyzeMarket,
    searchProducts,
    convertToUSD,
    markets: XBOX_MARKETS
  };
};

export default useXboxAPI;