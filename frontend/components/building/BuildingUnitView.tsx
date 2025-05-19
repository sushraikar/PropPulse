import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardContent, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { Sun, Moon, Info } from 'lucide-react';

// Sunset view score color ranges
const SUNSET_SCORE_COLORS = {
  low: '#FF6B6B',    // Red (0-33)
  medium: '#FFC65C', // Yellow (34-66)
  high: '#27AE60'    // Green (67-100)
};

// Get color based on sunset view score
const getSunsetScoreColor = (score) => {
  if (score >= 67) return SUNSET_SCORE_COLORS.high;
  if (score >= 34) return SUNSET_SCORE_COLORS.medium;
  return SUNSET_SCORE_COLORS.low;
};

const BuildingUnitView = ({ propertyId, projectCode }) => {
  const { toast } = useToast();
  const [buildingData, setBuildingData] = useState(null);
  const [selectedFloor, setSelectedFloor] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeView, setActiveView] = useState('sunset');

  // Fetch building data
  useEffect(() => {
    const fetchBuildingData = async () => {
      if (!projectCode) return;
      
      try {
        setIsLoading(true);
        
        // Fetch building units data
        const response = await fetch(`/api/projects/${projectCode}/building-units`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch building units data');
        }
        
        const data = await response.json();
        setBuildingData(data);
        
        // Set default selected floor to the middle floor
        if (data.floors && data.floors.length > 0) {
          const middleFloorIndex = Math.floor(data.floors.length / 2);
          setSelectedFloor(data.floors[middleFloorIndex]);
        }
        
      } catch (error) {
        console.error('Error fetching building data:', error);
        toast({
          title: 'Error',
          description: 'Failed to load building units data',
          variant: 'destructive'
        });
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchBuildingData();
  }, [projectCode, toast]);

  // Handle floor selection
  const handleFloorSelect = (floor) => {
    setSelectedFloor(floor);
  };

  // Render loading state
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Building Units</CardTitle>
          <CardDescription>Loading building data...</CardDescription>
        </CardHeader>
        <CardContent>
          <Skeleton className="w-full h-[500px]" />
        </CardContent>
      </Card>
    );
  }

  // Render error state if no building data
  if (!buildingData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Building Units</CardTitle>
          <CardDescription>No building data available</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[500px] bg-muted/20 rounded-md">
            <div className="text-center">
              <Info className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-2 text-lg font-medium">No building data</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Building data is not available for this project.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Get units for the selected floor
  const floorUnits = selectedFloor 
    ? buildingData.units.filter(unit => unit.floor === selectedFloor.number)
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{buildingData.project_name}</CardTitle>
        <CardDescription>
          {buildingData.tower_phase || 'Building'} Units View
        </CardDescription>
        
        <Tabs defaultValue="sunset" onValueChange={setActiveView} value={activeView}>
          <TabsList>
            <TabsTrigger value="sunset">
              <Sun className="h-4 w-4 mr-2" />
              Sunset View
            </TabsTrigger>
            <TabsTrigger value="availability">
              <Moon className="h-4 w-4 mr-2" />
              Availability
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </CardHeader>
      
      <CardContent>
        <div className="flex flex-col md:flex-row gap-4">
          {/* Floor Selector */}
          <div className="w-full md:w-24 mb-4 md:mb-0">
            <h3 className="font-medium text-sm mb-2">Floor</h3>
            <div className="flex flex-row md:flex-col gap-1 max-h-[500px] overflow-y-auto">
              {buildingData.floors.slice().reverse().map((floor) => (
                <button
                  key={floor.number}
                  className={`
                    p-2 text-center rounded-md transition-colors
                    ${selectedFloor?.number === floor.number 
                      ? 'bg-primary text-primary-foreground' 
                      : 'bg-muted hover:bg-muted/80'}
                  `}
                  onClick={() => handleFloorSelect(floor)}
                >
                  {floor.number}
                </button>
              ))}
            </div>
          </div>
          
          {/* Building View */}
          <div className="flex-1">
            <div className="relative bg-muted/20 rounded-md p-4 h-[500px] overflow-auto">
              {/* Floor Title */}
              <div className="text-center mb-4">
                <h3 className="text-lg font-medium">
                  Floor {selectedFloor?.number || ''}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {floorUnits.length} units
                </p>
              </div>
              
              {/* Color Legend */}
              {activeView === 'sunset' && (
                <div className="absolute top-4 right-4 bg-background/90 p-2 rounded-md border shadow-sm">
                  <h4 className="text-xs font-medium mb-1">Sunset View Score</h4>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: SUNSET_SCORE_COLORS.high }}></span>
                    <span>67-100</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: SUNSET_SCORE_COLORS.medium }}></span>
                    <span>34-66</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: SUNSET_SCORE_COLORS.low }}></span>
                    <span>0-33</span>
                  </div>
                </div>
              )}
              
              {/* Units Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-4">
                {floorUnits.map((unit) => {
                  // Determine unit color based on active view
                  let backgroundColor = 'bg-muted';
                  let textColor = 'text-foreground';
                  let borderColor = 'border-border';
                  
                  if (activeView === 'sunset') {
                    backgroundColor = getSunsetScoreColor(unit.sunset_view_score);
                    textColor = unit.sunset_view_score >= 50 ? 'text-white' : 'text-black';
                    borderColor = 'border-transparent';
                  } else if (activeView === 'availability') {
                    if (unit.status === 'Available') {
                      backgroundColor = '#4CAF50'; // Green
                      textColor = 'text-white';
                      borderColor = 'border-transparent';
                    } else if (unit.status === 'Booked') {
                      backgroundColor = '#FFC107'; // Yellow
                      textColor = 'text-black';
                      borderColor = 'border-transparent';
                    } else if (unit.status === 'Sold') {
                      backgroundColor = '#F44336'; // Red
                      textColor = 'text-white';
                      borderColor = 'border-transparent';
                    }
                  }
                  
                  // Highlight current property
                  const isCurrentProperty = propertyId && unit.property_id === propertyId;
                  
                  return (
                    <div
                      key={unit.unit_no}
                      className={`
                        relative p-3 rounded-md border ${borderColor} transition-all
                        ${isCurrentProperty ? 'ring-2 ring-primary ring-offset-2' : ''}
                      `}
                      style={{ 
                        backgroundColor,
                        color: textColor
                      }}
                    >
                      <div className="text-center">
                        <h4 className="font-medium">{unit.unit_no}</h4>
                        <p className="text-xs opacity-90">{unit.unit_type || 'Unit'}</p>
                        
                        {activeView === 'sunset' && (
                          <div className="mt-1 text-xs font-medium">
                            {unit.sunset_view_score}/100
                          </div>
                        )}
                        
                        {activeView === 'availability' && (
                          <div className="mt-1 text-xs font-medium">
                            {unit.status || 'Unknown'}
                          </div>
                        )}
                        
                        <div className="mt-1 text-xs opacity-75">
                          {unit.size_ft2} ft²
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              
              {/* Empty State */}
              {floorUnits.length === 0 && (
                <div className="flex items-center justify-center h-[300px]">
                  <div className="text-center">
                    <Info className="mx-auto h-8 w-8 text-muted-foreground" />
                    <p className="mt-2 text-sm text-muted-foreground">
                      No units found for this floor
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default BuildingUnitView;
