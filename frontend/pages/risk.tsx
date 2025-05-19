import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Heading, 
  Flex, 
  Select, 
  Text, 
  Button, 
  Tooltip, 
  useColorModeValue,
  Grid,
  GridItem,
  Badge,
  Spinner,
  Stack
} from '@chakra-ui/react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as RechartsTooltip, 
  ResponsiveContainer,
  Legend,
  ReferenceLine
} from 'recharts';
import { DownloadIcon, InfoIcon } from '@chakra-ui/icons';
import { useTranslation } from 'next-i18next';
import axios from 'axios';

import DashboardLayout from '../layouts/DashboardLayout';
import HeatMapChart from '../charts/HeatMapChart';
import RiskGradeBadge from '../common/RiskGradeBadge';

const UnderwriterDashboard = () => {
  const { t } = useTranslation('common');
  const [loading, setLoading] = useState(true);
  const [properties, setProperties] = useState([]);
  const [selectedProperty, setSelectedProperty] = useState('');
  const [riskData, setRiskData] = useState(null);
  const [irrDistribution, setIrrDistribution] = useState([]);
  const [heatMapData, setHeatMapData] = useState([]);
  const [filters, setFilters] = useState({
    tower: 'all',
    floor: 'all',
    unitType: 'all',
    riskGrade: 'all'
  });
  
  const [towers, setTowers] = useState([]);
  const [floors, setFloors] = useState([]);
  const [unitTypes, setUnitTypes] = useState([]);
  
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  
  // Color scheme for risk grades
  const riskColors = {
    green: '#27AE60',
    amber: '#FFC65C',
    red: '#FF6B6B'
  };

  useEffect(() => {
    // Fetch properties on component mount
    fetchProperties();
  }, []);

  useEffect(() => {
    // Fetch risk data when a property is selected
    if (selectedProperty) {
      fetchRiskData(selectedProperty);
    }
  }, [selectedProperty]);

  useEffect(() => {
    // Update heat map data when filters change
    if (properties.length > 0) {
      generateHeatMapData();
    }
  }, [filters, properties]);

  const fetchProperties = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/properties');
      setProperties(response.data.properties);
      
      // Extract unique towers, floors, and unit types
      const uniqueTowers = [...new Set(response.data.properties.map(p => p.tower))];
      const uniqueFloors = [...new Set(response.data.properties.map(p => p.floor))].sort((a, b) => b - a); // Sort floors in descending order
      const uniqueUnitTypes = [...new Set(response.data.properties.map(p => p.unit_type))];
      
      setTowers(uniqueTowers);
      setFloors(uniqueFloors);
      setUnitTypes(uniqueUnitTypes);
      
      // Set default selected property if available
      if (response.data.properties.length > 0) {
        setSelectedProperty(response.data.properties[0].id);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching properties:', error);
      setLoading(false);
    }
  };

  const fetchRiskData = async (propertyId) => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/risk/${propertyId}`);
      setRiskData(response.data);
      
      // Generate IRR distribution data for tornado chart
      if (response.data.simulation_results && response.data.simulation_results.irr_histogram) {
        generateIrrDistribution(response.data);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching risk data:', error);
      setLoading(false);
    }
  };

  const generateIrrDistribution = (data) => {
    // Create data for tornado chart from histogram
    const histogram = data.simulation_results.irr_histogram;
    const percentiles = data.simulation_results.irr_percentiles;
    
    // Create 20 bins for the distribution
    const binSize = (percentiles['95'] - percentiles['5']) / 20;
    const startValue = percentiles['5'] - binSize;
    
    const distributionData = [];
    
    for (let i = 0; i < histogram.length; i++) {
      const binStart = startValue + (i * binSize);
      const binEnd = binStart + binSize;
      const binCenter = (binStart + binEnd) / 2;
      
      distributionData.push({
        irr: binCenter * 100, // Convert to percentage
        frequency: histogram[i],
        binStart: binStart * 100,
        binEnd: binEnd * 100
      });
    }
    
    setIrrDistribution(distributionData);
  };

  const generateHeatMapData = () => {
    // Filter properties based on selected filters
    let filteredProperties = [...properties];
    
    if (filters.tower !== 'all') {
      filteredProperties = filteredProperties.filter(p => p.tower === filters.tower);
    }
    
    if (filters.unitType !== 'all') {
      filteredProperties = filteredProperties.filter(p => p.unit_type === filters.unitType);
    }
    
    if (filters.riskGrade !== 'all') {
      filteredProperties = filteredProperties.filter(p => p.risk_grade === filters.riskGrade);
    }
    
    // Group properties by floor and unit position
    const heatMapData = [];
    
    // Get unique floors and unit positions
    const uniqueFloors = [...new Set(filteredProperties.map(p => p.floor))].sort((a, b) => b - a);
    const uniquePositions = [...new Set(filteredProperties.map(p => p.unit_position))].sort();
    
    // Create heat map data
    uniqueFloors.forEach(floor => {
      const floorUnits = [];
      
      uniquePositions.forEach(position => {
        const unit = filteredProperties.find(p => p.floor === floor && p.unit_position === position);
        
        if (unit) {
          floorUnits.push({
            id: unit.id,
            value: unit.risk_grade === 'green' ? 100 : (unit.risk_grade === 'amber' ? 50 : 0),
            riskGrade: unit.risk_grade,
            meanIrr: unit.mean_irr,
            var5: unit.var_5,
            unitNo: unit.id
          });
        } else {
          floorUnits.push({
            id: `empty-${floor}-${position}`,
            value: null,
            riskGrade: null,
            meanIrr: null,
            var5: null,
            unitNo: null
          });
        }
      });
      
      heatMapData.push({
        floor,
        units: floorUnits
      });
    });
    
    setHeatMapData(heatMapData);
  };

  const handleFilterChange = (filterName, value) => {
    setFilters({
      ...filters,
      [filterName]: value
    });
  };

  const handlePropertyChange = (e) => {
    setSelectedProperty(e.target.value);
  };

  const exportCsv = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/risk/${selectedProperty}/export`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `risk_simulation_${selectedProperty}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      setLoading(false);
    } catch (error) {
      console.error('Error exporting CSV:', error);
      setLoading(false);
    }
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <Box bg={bgColor} p={3} border="1px solid" borderColor={borderColor} borderRadius="md" boxShadow="md">
          <Text fontWeight="bold">{`IRR: ${payload[0].payload.binStart.toFixed(1)}% to ${payload[0].payload.binEnd.toFixed(1)}%`}</Text>
          <Text>{`Frequency: ${payload[0].value}`}</Text>
          <Text fontSize="sm" color="gray.500">{`Percentile: ${(payload[0].payload.frequency / irrDistribution.reduce((sum, item) => sum + item.frequency, 0) * 100).toFixed(1)}%`}</Text>
        </Box>
      );
    }
    return null;
  };

  return (
    <DashboardLayout>
      <Box p={5}>
        <Heading mb={5}>{t('underwriter_dashboard')}</Heading>
        
        {/* Filters */}
        <Flex mb={5} wrap="wrap" gap={4}>
          <Box minW="200px">
            <Text mb={2}>{t('property')}</Text>
            <Select value={selectedProperty} onChange={handlePropertyChange}>
              {properties.map(property => (
                <option key={property.id} value={property.id}>{property.id}</option>
              ))}
            </Select>
          </Box>
          
          <Box minW="150px">
            <Text mb={2}>{t('tower')}</Text>
            <Select value={filters.tower} onChange={(e) => handleFilterChange('tower', e.target.value)}>
              <option value="all">{t('all')}</option>
              {towers.map(tower => (
                <option key={tower} value={tower}>{tower}</option>
              ))}
            </Select>
          </Box>
          
          <Box minW="150px">
            <Text mb={2}>{t('floor')}</Text>
            <Select value={filters.floor} onChange={(e) => handleFilterChange('floor', e.target.value)}>
              <option value="all">{t('all')}</option>
              {floors.map(floor => (
                <option key={floor} value={floor}>{floor}</option>
              ))}
            </Select>
          </Box>
          
          <Box minW="150px">
            <Text mb={2}>{t('unit_type')}</Text>
            <Select value={filters.unitType} onChange={(e) => handleFilterChange('unitType', e.target.value)}>
              <option value="all">{t('all')}</option>
              {unitTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </Select>
          </Box>
          
          <Box minW="150px">
            <Text mb={2}>{t('risk_grade')}</Text>
            <Select value={filters.riskGrade} onChange={(e) => handleFilterChange('riskGrade', e.target.value)}>
              <option value="all">{t('all')}</option>
              <option value="green">{t('green')}</option>
              <option value="amber">{t('amber')}</option>
              <option value="red">{t('red')}</option>
            </Select>
          </Box>
        </Flex>
        
        {loading ? (
          <Flex justify="center" align="center" h="400px">
            <Spinner size="xl" />
          </Flex>
        ) : (
          <>
            {/* Risk Summary */}
            {riskData && (
              <Grid templateColumns={{ base: "repeat(1, 1fr)", md: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" }} gap={6} mb={8}>
                <GridItem>
                  <Box p={5} bg={bgColor} borderRadius="md" boxShadow="sm" border="1px solid" borderColor={borderColor}>
                    <Flex justify="space-between" align="center" mb={2}>
                      <Text fontSize="sm" color="gray.500">{t('risk_grade')}</Text>
                      <Tooltip label={t('risk_grade_tooltip')}>
                        <InfoIcon color="gray.400" />
                      </Tooltip>
                    </Flex>
                    <Flex align="center">
                      <RiskGradeBadge grade={riskData.risk_grade} size="lg" />
                      <Text ml={2} fontSize="lg" fontWeight="bold">{riskData.risk_grade.toUpperCase()}</Text>
                    </Flex>
                  </Box>
                </GridItem>
                
                <GridItem>
                  <Box p={5} bg={bgColor} borderRadius="md" boxShadow="sm" border="1px solid" borderColor={borderColor}>
                    <Flex justify="space-between" align="center" mb={2}>
                      <Text fontSize="sm" color="gray.500">{t('mean_irr')}</Text>
                      <Tooltip label={t('mean_irr_tooltip')}>
                        <InfoIcon color="gray.400" />
                      </Tooltip>
                    </Flex>
                    <Text fontSize="2xl" fontWeight="bold">{(riskData.mean_irr * 100).toFixed(1)}%</Text>
                  </Box>
                </GridItem>
                
                <GridItem>
                  <Box p={5} bg={bgColor} borderRadius="md" boxShadow="sm" border="1px solid" borderColor={borderColor}>
                    <Flex justify="space-between" align="center" mb={2}>
                      <Text fontSize="sm" color="gray.500">{t('var_5')}</Text>
                      <Tooltip label={t('var_5_tooltip')}>
                        <InfoIcon color="gray.400" />
                      </Tooltip>
                    </Flex>
                    <Text fontSize="2xl" fontWeight="bold">{(riskData.var_5 * 100).toFixed(1)}%</Text>
                  </Box>
                </GridItem>
                
                <GridItem>
                  <Box p={5} bg={bgColor} borderRadius="md" boxShadow="sm" border="1px solid" borderColor={borderColor}>
                    <Flex justify="space-between" align="center" mb={2}>
                      <Text fontSize="sm" color="gray.500">{t('prob_negative')}</Text>
                      <Tooltip label={t('prob_negative_tooltip')}>
                        <InfoIcon color="gray.400" />
                      </Tooltip>
                    </Flex>
                    <Text fontSize="2xl" fontWeight="bold">{(riskData.prob_negative * 100).toFixed(1)}%</Text>
                  </Box>
                </GridItem>
              </Grid>
            )}
            
            {/* Tornado Diagram */}
            {irrDistribution.length > 0 && (
              <Box mb={8} p={5} bg={bgColor} borderRadius="md" boxShadow="sm" border="1px solid" borderColor={borderColor}>
                <Flex justify="space-between" align="center" mb={4}>
                  <Heading size="md">{t('irr_distribution')}</Heading>
                  <Button leftIcon={<DownloadIcon />} onClick={exportCsv} size="sm">
                    {t('export_csv')}
                  </Button>
                </Flex>
                
                <Box h="400px">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={irrDistribution}
                      margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="irr" 
                        label={{ value: 'IRR (%)', position: 'insideBottomRight', offset: -5 }}
                        tickFormatter={(value) => value.toFixed(0)}
                      />
                      <YAxis 
                        label={{ value: 'Frequency', angle: -90, position: 'insideLeft' }}
                      />
                      <RechartsTooltip content={<CustomTooltip />} />
                      <Legend />
                      <ReferenceLine x={0} stroke="#000" />
                      <ReferenceLine 
                        x={(riskData?.mean_irr || 0) * 100} 
                        stroke="#8884d8" 
                        label={{ value: 'Mean', position: 'top' }} 
                      />
                      <Bar 
                        dataKey="frequency" 
                        fill="#8884d8" 
                        name="Frequency"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </Box>
            )}
            
            {/* Heat Map */}
            {heatMapData.length > 0 && (
              <Box mb={8} p={5} bg={bgColor} borderRadius="md" boxShadow="sm" border="1px solid" borderColor={borderColor}>
                <Heading size="md" mb={4}>{t('risk_heatmap')}</Heading>
                
                <Box h="500px">
                  <HeatMapChart 
                    data={heatMapData} 
                    colorScale={[riskColors.red, riskColors.amber, riskColors.green]}
                    tooltipContent={(cell) => (
                      <Box>
                        <Text fontWeight="bold">{cell.unitNo || 'Empty'}</Text>
                        {cell.riskGrade && (
                          <>
                            <Text>{`Risk Grade: ${cell.riskGrade.toUpperCase()}`}</Text>
                            <Text>{`Mean IRR: ${(cell.meanIrr * 100).toFixed(1)}%`}</Text>
                            <Text>{`VaR (5%): ${(cell.var5 * 100).toFixed(1)}%`}</Text>
                          </>
                        )}
                      </Box>
                    )}
                  />
                </Box>
                
                <Flex mt={4} justify="center">
                  <Stack direction="row" spacing={4}>
                    <Flex align="center">
                      <Box w="20px" h="20px" bg={riskColors.red} borderRadius="sm" mr={2} />
                      <Text>{t('red')}</Text>
                    </Flex>
                    <Flex align="center">
                      <Box w="20px" h="20px" bg={riskColors.amber} borderRadius="sm" mr={2} />
                      <Text>{t('amber')}</Text>
                    </Flex>
                    <Flex align="center">
                      <Box w="20px" h="20px" bg={riskColors.green} borderRadius="sm" mr={2} />
                      <Text>{t('green')}</Text>
                    </Flex>
                  </Stack>
                </Flex>
              </Box>
            )}
          </>
        )}
      </Box>
    </DashboardLayout>
  );
};

export default UnderwriterDashboard;
