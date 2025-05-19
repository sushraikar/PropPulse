import React, { useState, useEffect, useRef } from 'react';
import { GoogleMap, useJsApiLoader, Marker, InfoWindow } from '@react-google-maps/api';
import { Card, CardHeader, CardContent, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { MapPin, Star, Navigation, Info } from 'lucide-react';

// POI category icons and colors
const poiIcons = {
  casino: { icon: '🎰', color: '#FF5722' },
  hotel: { icon: '🏨', color: '#2196F3' },
  beach: { icon: '🏖️', color: '#FFC107' },
  marina: { icon: '⚓', color: '#3F51B5' },
  restaurant: { icon: '🍽️', color: '#E91E63' },
  hospital: { icon: '🏥', color: '#4CAF50' },
  school: { icon: '🏫', color: '#9C27B0' },
  golf_course: { icon: '⛳', color: '#8BC34A' },
  water_park: { icon: '🌊', color: '#00BCD4' }
};

// POI category labels
const poiLabels = {
  casino: 'Casinos & Gaming',
  hotel: 'Hotels & Resorts',
  beach: 'Beaches & Beach Clubs',
  marina: 'Marinas & Yacht Clubs',
  restaurant: 'Fine Dining',
  hospital: 'Hospitals & Clinics',
  school: 'International Schools',
  golf_course: 'Golf Courses',
  water_park: 'Water Parks'
};

const containerStyle = {
  width: '100%',
  height: '600px'
};

const defaultCenter = {
  lat: 25.7406, // Wynn Casino site
  lng: 55.8350
};

const MapWidget = ({ propertyId }) => {
  const { toast } = useToast();
  const [property, setProperty] = useState(null);
  const [poiData, setPOIData] = useState({});
  const [selectedPOI, setSelectedPOI] = useState(null);
  const [activeCategories, setActiveCategories] = useState(Object.keys(poiLabels));
  const [isLoading, setIsLoading] = useState(true);
  const [mapCenter, setMapCenter] = useState(defaultCenter);
  const mapRef = useRef(null);

  // Load Google Maps API
  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
  });

  // Fetch property data and POIs
  useEffect(() => {
    const fetchPropertyData = async () => {
      if (!propertyId) return;
      
      try {
        setIsLoading(true);
        
        // Fetch property location data
        const response = await fetch(`/api/properties/${propertyId}/location`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch property location data');
        }
        
        const data = await response.json();
        
        setProperty(data.property);
        setPOIData(data.poi_data || {});
        
        // Set map center to property location if available
        if (data.property?.latitude && data.property?.longitude) {
          setMapCenter({
            lat: data.property.latitude,
            lng: data.property.longitude
          });
        }
        
      } catch (error) {
        console.error('Error fetching property data:', error);
        toast({
          title: 'Error',
          description: 'Failed to load property location data',
          variant: 'destructive'
        });
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchPropertyData();
  }, [propertyId, toast]);

  // Toggle POI category
  const toggleCategory = (category) => {
    setActiveCategories(prev => 
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  // Handle map load
  const onMapLoad = (map) => {
    mapRef.current = map;
  };

  // Handle POI click
  const handlePOIClick = (poi) => {
    setSelectedPOI(poi);
  };

  // Get all visible POIs
  const getVisiblePOIs = () => {
    return Object.entries(poiData)
      .filter(([category]) => activeCategories.includes(category))
      .flatMap(([category, pois]) => 
        pois.map(poi => ({
          ...poi,
          category
        }))
      );
  };

  // Render loading state
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Location Intelligence</CardTitle>
          <CardDescription>Loading property location data...</CardDescription>
        </CardHeader>
        <CardContent>
          <Skeleton className="w-full h-[600px]" />
        </CardContent>
      </Card>
    );
  }

  // Render error state if no property data
  if (!property) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Location Intelligence</CardTitle>
          <CardDescription>No location data available</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[600px] bg-muted/20 rounded-md">
            <div className="text-center">
              <Info className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-2 text-lg font-medium">No location data</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Location data is not available for this property.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Location Intelligence</CardTitle>
        <CardDescription>
          {property.project_name} - Unit {property.unit_no}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col md:flex-row gap-4">
          {/* POI Category Toggles */}
          <div className="w-full md:w-64 space-y-4 mb-4 md:mb-0">
            <h3 className="font-medium">Points of Interest</h3>
            <div className="space-y-2">
              {Object.entries(poiLabels).map(([category, label]) => (
                <div key={category} className="flex items-center space-x-2">
                  <Checkbox 
                    id={`category-${category}`}
                    checked={activeCategories.includes(category)}
                    onCheckedChange={() => toggleCategory(category)}
                  />
                  <Label 
                    htmlFor={`category-${category}`}
                    className="flex items-center cursor-pointer"
                  >
                    <span className="mr-2">{poiIcons[category]?.icon}</span>
                    {label}
                  </Label>
                </div>
              ))}
            </div>
            
            {/* Property Info */}
            <div className="mt-6 p-4 border rounded-md">
              <h3 className="font-medium mb-2">Property Details</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Coordinates:</span>
                  <span>{property.latitude.toFixed(6)}, {property.longitude.toFixed(6)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">View Orientation:</span>
                  <span>{property.view_orientation || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Sunset Score:</span>
                  <span>{property.sunset_view_score}/100</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Wynn Distance:</span>
                  <span>{property.wynn_casino_distance?.toFixed(2)} km</span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Map */}
          <div className="flex-1">
            {isLoaded ? (
              <GoogleMap
                mapContainerStyle={containerStyle}
                center={mapCenter}
                zoom={14}
                onLoad={onMapLoad}
                options={{
                  mapTypeControl: false,
                  streetViewControl: false,
                  fullscreenControl: true,
                  zoomControl: true,
                }}
              >
                {/* Property Marker */}
                <Marker
                  position={{
                    lat: property.latitude,
                    lng: property.longitude
                  }}
                  icon={{
                    path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
                    fillColor: '#4f46e5',
                    fillOpacity: 1,
                    strokeWeight: 1,
                    strokeColor: '#ffffff',
                    scale: 2,
                    anchor: { x: 12, y: 22 },
                  }}
                  title={`${property.project_name} - Unit ${property.unit_no}`}
                />
                
                {/* Wynn Casino Marker */}
                <Marker
                  position={{
                    lat: 25.7406,
                    lng: 55.8350
                  }}
                  icon={{
                    path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
                    fillColor: '#FF5722',
                    fillOpacity: 1,
                    strokeWeight: 1,
                    strokeColor: '#ffffff',
                    scale: 2,
                    anchor: { x: 12, y: 22 },
                  }}
                  title="Wynn Casino Site"
                />
                
                {/* POI Markers */}
                {getVisiblePOIs().map((poi, index) => (
                  <Marker
                    key={`${poi.category}-${index}`}
                    position={{
                      lat: poi.latitude,
                      lng: poi.longitude
                    }}
                    onClick={() => handlePOIClick(poi)}
                    icon={{
                      path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
                      fillColor: poiIcons[poi.category]?.color || '#000000',
                      fillOpacity: 0.8,
                      strokeWeight: 1,
                      strokeColor: '#ffffff',
                      scale: 1.5,
                      anchor: { x: 12, y: 22 },
                    }}
                    title={poi.name}
                  />
                ))}
                
                {/* Info Window for selected POI */}
                {selectedPOI && (
                  <InfoWindow
                    position={{
                      lat: selectedPOI.latitude,
                      lng: selectedPOI.longitude
                    }}
                    onCloseClick={() => setSelectedPOI(null)}
                  >
                    <div className="p-1">
                      <h3 className="font-medium text-base">{selectedPOI.name}</h3>
                      <div className="mt-1 space-y-1 text-sm">
                        <div className="flex items-center">
                          <MapPin className="h-3 w-3 mr-1 text-muted-foreground" />
                          <span>{selectedPOI.distance.toFixed(2)} km away</span>
                        </div>
                        {selectedPOI.rating && (
                          <div className="flex items-center">
                            <Star className="h-3 w-3 mr-1 text-amber-500" />
                            <span>{selectedPOI.rating}/5</span>
                            {selectedPOI.user_ratings_total && (
                              <span className="text-xs text-muted-foreground ml-1">
                                ({selectedPOI.user_ratings_total})
                              </span>
                            )}
                          </div>
                        )}
                        <div>
                          <Badge variant="outline" className="mt-1">
                            {poiLabels[selectedPOI.category]}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </InfoWindow>
                )}
              </GoogleMap>
            ) : (
              <div className="w-full h-[600px] flex items-center justify-center bg-muted/20 rounded-md">
                <div className="text-center">
                  <span className="block animate-spin rounded-full h-10 w-10 border-4 border-primary border-r-transparent mx-auto"></span>
                  <p className="mt-2 text-sm text-muted-foreground">Loading map...</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default MapWidget;
