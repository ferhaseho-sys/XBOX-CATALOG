import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Alert, AlertDescription } from './ui/alert';
import { Separator } from './ui/separator';
import { 
  Search, 
  ExternalLink, 
  Image as ImageIcon, 
  Info, 
  DollarSign, 
  Calendar, 
  Gamepad2,
  Globe,
  Star,
  Download,
  Copy,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { useXboxAPI, XBOX_MARKETS } from '../hooks/useXboxAPI';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { ProductDetails } from '../types/scraper';

// Enhanced Xbox game data interface for the viewer
interface XboxGameData {
  productId: string;
  title: string;
  description: string;
  price: number;
  currency: string;
  region: string;
  locale: string;
  developer: string;
  publisher: string;
  releaseDate: string;
  rating: number;
  discount: number;
  isOnSale: boolean;
  categories: string[];
  platforms: string[];
  features: string[];
  images: {
    poster?: string;
    thumbnail?: string;
    screenshots: string[];
  };
  availability: {
    skuId: string;
    availabilityId: string;
    available: boolean;
  };
  storeUrl: string;
}

export function XboxProductViewer() {
  const [productId, setProductId] = useState('9NGBNVMFXPT6'); // Default to Halo Infinite
  const [selectedRegion, setSelectedRegion] = useState('US');
  const [selectedLanguage, setSelectedLanguage] = useState('en-US');
  const [gameData, setGameData] = useState<XboxGameData | null>(null);
  const [searchHistory, setSearchHistory] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  const { loading, error, searchProducts, convertToUSD } = useXboxAPI();

  // Language options
  const languages = [
    { code: 'en-US', name: 'English (US)' },
    { code: 'en-GB', name: 'English (UK)' },
    { code: 'es-AR', name: 'Español (Argentina)' },
    { code: 'es-ES', name: 'Español (España)' },
    { code: 'es-MX', name: 'Español (México)' },
    { code: 'pt-BR', name: 'Português (Brasil)' },
    { code: 'fr-FR', name: 'Français (France)' },
    { code: 'de-DE', name: 'Deutsch (Deutschland)' },
    { code: 'it-IT', name: 'Italiano (Italia)' },
    { code: 'ja-JP', name: '日本語 (日本)' },
    { code: 'ko-KR', name: '한국어 (한국)' },
    { code: 'zh-CN', name: '中文 (简体)' },
    { code: 'zh-TW', name: '中文 (繁體)' },
    { code: 'ru-RU', name: 'Русский (Россия)' },
    { code: 'tr-TR', name: 'Türkçe (Türkiye)' },
    { code: 'ar-SA', name: 'العربية (السعودية)' }
  ];

  // Get favorite regions (most commonly used)
  const favoriteRegions = ['US', 'GB', 'DE', 'FR', 'JP', 'AU', 'CA', 'BR', 'MX', 'AR'];
  const allRegions = XBOX_MARKETS.map(market => market.code);

  // Helper function to get language for region
  const getLanguageForRegion = useCallback((region: string): string => {
    const market = XBOX_MARKETS.find(m => m.code === region);
    return market?.locale || 'en-US';
  }, []);

  // Helper function to get currency for region
  const getCurrencyForRegion = useCallback((region: string): string => {
    const market = XBOX_MARKETS.find(m => m.code === region);
    return market?.currency || 'USD';
  }, []);

  // Add to favorites
  const addToFavorites = useCallback((region: string) => {
    // In a real app, this would save to localStorage or user preferences
    addLog(`⭐ Added ${region} to favorites`);
  }, []);

  // Add log entry
  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [`[${timestamp}] ${message}`, ...prev.slice(0, 49)]); // Keep last 50 logs
  }, []);

  // Mock function to check product availability
  const checkProductAvailability = useCallback(async (productId: string, region: string) => {
    // Simulate API call delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    return {
      available: true,
      reason: null
    };
  }, []);

  // Datos REALES desde la API de Atlas (metadata + precio de la región)
  const fetchGameData = useCallback(async (productId: string, region: string): Promise<XboxGameData | null> => {
    const ATLAS_API = (import.meta as any).env?.VITE_ATLAS_API || 'http://127.0.0.1:8000';
    try {
      const p = await fetch(`${ATLAS_API}/api/product/${productId}?market=${region}`)
        .then(r => (r.ok ? r.json() : null));
      if (!p || !p.product_id) return null;
      const prices = p.prices || [];
      const row: any = prices.find((r: any) => r.market === region) || prices[0] || {};
      return {
        productId: p.product_id,
        title: p.title || productId,
        description: p.description || p.short_desc || '',
        price: row.list_price != null ? Number(row.list_price) : 0,
        currency: row.currency || getCurrencyForRegion(region),
        region,
        locale: getLanguageForRegion(region),
        developer: p.developer || '',
        publisher: p.publisher || '',
        releaseDate: p.release_date || '',
        rating: p.avg_rating || 0,
        discount: row.discount_pct || 0,
        isOnSale: !!row.on_sale,
        categories: (p.categories && p.categories.length) ? p.categories : (p.category ? [p.category] : []),
        platforms: (p.console_gen && p.console_gen.length) ? p.console_gen : ['Xbox'],
        features: [],
        images: {
          poster: p.image_poster || p.image_boxart || '',
          thumbnail: p.image_boxart || '',
          screenshots: []
        },
        availability: { skuId: '', availabilityId: '', available: prices.length > 0 },
        storeUrl: `https://www.xbox.com/games/store/${productId}`,
        priceUSD: row.price_usd,
        variants: p.variants || []
      } as any;
    } catch {
      return null;
    }
  }, [getCurrencyForRegion, getLanguageForRegion]);

  // Search function
  const searchProduct = useCallback(async () => {
    if (!productId.trim()) {
      addLog('❌ Please enter a Product ID');
      return;
    }

    setIsLoading(true);
    setGameData(null);
    addLog(`🔍 Searching for product: ${productId} in region: ${selectedRegion}`);

    try {
      // Check availability first
      const availability = await checkProductAvailability(productId, selectedRegion);
      addLog(`📋 Product availability: ${availability.available ? 'Available' : 'Not available'}`);
      
      if (!availability.available && availability.reason) {
        addLog(`⚠️ ${availability.reason}`);
      }

      // Fetch full game data
      const data = await fetchGameData(productId, selectedRegion);
      
      if (data) {
        setGameData(data);
        addLog(`✅ Successfully loaded: ${data.title}`);
        addLog(`💰 Price: ${data.price} ${data.currency}`);
        addLog(`🏷️ Developer: ${data.developer}`);
        addLog(`🏢 Publisher: ${data.publisher}`);
        
        // Add to search history
        setSearchHistory(prev => {
          const newHistory = [productId, ...prev.filter(id => id !== productId)];
          return newHistory.slice(0, 10); // Keep last 10 searches
        });
      } else {
        addLog(`❌ Failed to load product data for ${productId}`);
      }
    } catch (err) {
      addLog(`❌ Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  }, [productId, selectedRegion, fetchGameData, checkProductAvailability, addLog]);

  // Auto-update language when region changes
  useEffect(() => {
    const autoLanguage = getLanguageForRegion(selectedRegion);
    setSelectedLanguage(autoLanguage);
    addLog(`🌐 Auto-selected language: ${autoLanguage} for region: ${selectedRegion}`);
  }, [selectedRegion, getLanguageForRegion, addLog]);

  // Search on Enter key
  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      searchProduct();
    }
  };

  // Copy product data
  const copyProductData = () => {
    if (!gameData) return;

    const data = {
      productId: gameData.productId,
      title: gameData.title,
      price: `${gameData.price} ${gameData.currency}`,
      developer: gameData.developer,
      publisher: gameData.publisher,
      releaseDate: gameData.releaseDate,
      region: gameData.region,
      storeUrl: gameData.storeUrl
    };

    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    addLog('📋 Product data copied to clipboard');
  };

  // Quick search from history
  const quickSearch = (id: string) => {
    setProductId(id);
    setTimeout(searchProduct, 100);
  };

  // Load default product on mount
  useEffect(() => {
    if (productId && !gameData) {
      addLog('🚀 Loading default product...');
      searchProduct();
    }
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Search Controls */}
      <div className="lg:col-span-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gamepad2 className="h-5 w-5" />
              Xbox Product Viewer
              <Badge variant="outline">Enhanced API</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="productId">Product ID</Label>
                <Input
                  id="productId"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="9NGBNVMFXPT6"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="region">Region</Label>
                <Select value={selectedRegion} onValueChange={setSelectedRegion}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Favorites */}
                    {favoriteRegions.map(region => (
                      <SelectItem key={region} value={region}>
                        <span className="flex items-center gap-2">
                          <Star className="h-3 w-3 text-yellow-500" />
                          {region}
                        </span>
                      </SelectItem>
                    ))}
                    <Separator />
                    {/* All regions */}
                    {allRegions.filter(region => !favoriteRegions.includes(region)).map(region => (
                      <SelectItem key={region} value={region}>
                        {region}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="language">Language</Label>
                <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {languages.map(lang => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end gap-2">
                <Button 
                  onClick={searchProduct}
                  disabled={isLoading}
                  className="flex-1"
                >
                  {isLoading ? (
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="mr-2 h-4 w-4" />
                  )}
                  Search
                </Button>
                
                <Button
                  variant="outline"
                  onClick={() => addToFavorites(selectedRegion)}
                >
                  <Star className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Search History */}
            {searchHistory.length > 0 && (
              <div className="space-y-2">
                <Label>Recent Searches</Label>
                <div className="flex flex-wrap gap-2">
                  {searchHistory.map((id, index) => (
                    <Button
                      key={index}
                      variant="outline"
                      size="sm"
                      onClick={() => quickSearch(id)}
                    >
                      {id}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <Alert variant={error.includes("API access restricted") ? "default" : "destructive"}>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {error}
                  {error.includes("API access restricted") && (
                    <div className="mt-2 text-sm">
                      <p><strong>Why is this happening?</strong></p>
                      <p>Web browsers block cross-origin requests for security. The Xbox API doesn't allow direct access from web pages.</p>
                      <p className="mt-1"><strong>Solutions:</strong></p>
                      <ul className="list-disc list-inside ml-2">
                        <li>Use the desktop app for real API access</li>
                        <li>Explore the demo data to see the interface functionality</li>
                      </ul>
                    </div>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Product Image */}
      <div className="lg:col-span-1">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ImageIcon className="h-5 w-5" />
              Product Image
            </CardTitle>
          </CardHeader>
          <CardContent>
            {gameData?.images.poster || gameData?.images.thumbnail ? (
              <div className="space-y-4">
                <ImageWithFallback
                  src={gameData.images.poster || gameData.images.thumbnail}
                  alt={gameData.title}
                  className="w-full h-auto rounded-lg border"
                />
                
                {gameData.images.screenshots.length > 0 && (
                  <div className="space-y-2">
                    <Label>Screenshots</Label>
                    <ScrollArea className="h-32">
                      <div className="flex gap-2">
                        {gameData.images.screenshots.slice(0, 5).map((screenshot, index) => (
                          <ImageWithFallback
                            key={index}
                            src={screenshot}
                            alt={`Screenshot ${index + 1}`}
                            className="w-20 h-12 object-cover rounded border flex-shrink-0"
                          />
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                )}
              </div>
            ) : (
              <div className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                <div className="text-center text-muted-foreground">
                  <ImageIcon className="h-12 w-12 mx-auto mb-2" />
                  <p>No image available</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Product Information */}
      <div className="lg:col-span-2">
        {gameData ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{gameData.title}</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={copyProductData}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Copy Data
                  </Button>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(gameData.storeUrl, '_blank')}
                  >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Store
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Price and availability */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Price</Label>
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-4 w-4" />
                    <span className="font-bold">{gameData.price} {gameData.currency}</span>
                    {gameData.isOnSale && (
                      <Badge variant="destructive">{gameData.discount}% OFF</Badge>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Release Date</Label>
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    <span>{gameData.releaseDate || 'N/A'}</span>
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Region</Label>
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4" />
                    <span>{gameData.region}</span>
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Rating</Label>
                  <div className="flex items-center gap-2">
                    <Star className="h-4 w-4" />
                    <span>{gameData.rating || 'N/A'}</span>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Description */}
              {gameData.description && (
                <div className="space-y-2">
                  <Label>Description</Label>
                  <ScrollArea className="h-32 w-full border rounded p-3">
                    <p className="text-sm">{gameData.description}</p>
                  </ScrollArea>
                </div>
              )}

              {/* Developer and Publisher */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Developer</Label>
                  <p>{gameData.developer}</p>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Publisher</Label>
                  <p>{gameData.publisher}</p>
                </div>
              </div>

              {/* Platforms */}
              {gameData.platforms.length > 0 && (
                <div className="space-y-2">
                  <Label>Platforms</Label>
                  <div className="flex flex-wrap gap-2">
                    {gameData.platforms.map((platform, index) => (
                      <Badge key={index} variant="secondary">
                        {platform}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Categories */}
              {gameData.categories.length > 0 && (
                <div className="space-y-2">
                  <Label>Categories</Label>
                  <div className="flex flex-wrap gap-2">
                    {gameData.categories.map((category, index) => (
                      <Badge key={index} variant="outline">
                        {category}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Features */}
              {gameData.features.length > 0 && (
                <div className="space-y-2">
                  <Label>Features</Label>
                  <div className="flex flex-wrap gap-2">
                    {gameData.features.map((feature, index) => (
                      <Badge key={index} variant="outline">
                        {feature}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Technical Details */}
              <div className="space-y-2">
                <Label>Technical Details</Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                  <div>Product ID: <code>{gameData.productId}</code></div>
                  <div>SKU ID: <code>{gameData.availability.skuId}</code></div>
                  <div>Availability ID: <code>{gameData.availability.availabilityId}</code></div>
                  <div>Locale: <code>{gameData.locale}</code></div>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="py-12">
              <div className="text-center text-muted-foreground">
                <Info className="h-12 w-12 mx-auto mb-4" />
                <p>Enter a Product ID and click Search to view product details</p>
                <p className="text-sm mt-2">
                  Example: 9NGBNVMFXPT6, 9NBLGGH4R315, 9P3J32CTXLRZ
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Logs */}
      <div className="lg:col-span-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Search Logs</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setLogs([])}
              >
                Clear
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-32 w-full border rounded p-3">
              {logs.length > 0 ? (
                <div className="space-y-1">
                  {logs.map((log, index) => (
                    <div key={index} className="text-sm font-mono">
                      {log}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">No logs yet...</p>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}