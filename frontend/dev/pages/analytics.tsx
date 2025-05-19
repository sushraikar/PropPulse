import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { 
  LineChart, Line, BarChart, Bar, PieChart, Pie, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, 
  ResponsiveContainer, Cell
} from 'recharts';
import { 
  Card, CardContent, CardHeader, CardTitle, 
  CardDescription, CardFooter 
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { 
  Select, SelectContent, SelectItem, 
  SelectTrigger, SelectValue 
} from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { DatePickerWithRange } from '../components/ui/date-range-picker';
import { Calendar } from '../components/ui/calendar';
import { useToast } from '../components/ui/use-toast';
import { Loader2, Download, Mail, Calendar as CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { useAuth } from '../contexts/AuthContext';
import HeatMapChart from '../components/charts/HeatMapChart';

// Colors for charts
const COLORS = ['#1F4AFF', '#27AE60', '#FFC65C', '#FF6B6B', '#9B59B6'];
const RISK_COLORS = {
  'Green': '#27AE60',
  'Amber': '#FFC65C',
  'Red': '#FF6B6B'
};

const Analytics = () => {
  const router = useRouter();
  const { user } = useAuth();
  const { toast } = useToast();
  
  // State for filters
  const [timeFilter, setTimeFilter] = useState('weekly');
  const [dateRange, setDateRange] = useState({
    from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    to: new Date()
  });
  const [selectedProject, setSelectedProject] = useState('all');
  const [projects, setProjects] = useState([]);
  
  // State for data
  const [viewsData, setViewsData] = useState([]);
  const [savesData, setSavesData] = useState([]);
  const [tokenizedData, setTokenizedData] = useState([]);
  const [riskGradeData, setRiskGradeData] = useState([]);
  const [timeOnListingData, setTimeOnListingData] = useState([]);
  const [conversionData, setConversionData] = useState([]);
  const [tokensTraded, setTokensTraded] = useState([]);
  
  // State for loading
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);
  
  // State for email preferences
  const [emailPreferences, setEmailPreferences] = useState({
    enabled: true,
    frequency: 'weekly',
    day: 'monday',
    time: '08:00',
    timezone: 'GST',
    kpis: {
      views: true,
      saves: true,
      tokenized: true,
      riskGrade: true,
      timeOnListing: true,
      conversion: true,
      tokensTraded: true
    }
  });

  // Fetch projects on component mount
  useEffect(() => {
    if (user) {
      fetchProjects();
    }
  }, [user]);

  // Fetch data when filters change
  useEffect(() => {
    if (user && projects.length > 0) {
      fetchAnalyticsData();
    }
  }, [timeFilter, dateRange, selectedProject, user, projects]);

  // Fetch projects
  const fetchProjects = async () => {
    try {
      // In a real implementation, this would be an API call
      // For this example, we'll use mock data
      const mockProjects = [
        { id: 'project1', name: 'Uno Luxe' },
        { id: 'project2', name: 'Marina Heights' },
        { id: 'project3', name: 'Palm Residences' }
      ];
      
      setProjects(mockProjects);
      setSelectedProject(mockProjects[0].id);
    } catch (error) {
      console.error('Error fetching projects:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch projects. Please try again.',
        variant: 'destructive'
      });
    }
  };

  // Fetch analytics data
  const fetchAnalyticsData = async () => {
    setIsLoading(true);
    
    try {
      // In a real implementation, this would be an API call with proper filters
      // For this example, we'll use mock data
      
      // Generate dates for x-axis based on time filter
      const dates = generateDates();
      
      // Mock data for views
      const mockViewsData = dates.map(date => ({
        date,
        views: Math.floor(Math.random() * 100) + 20
      }));
      
      // Mock data for saves
      const mockSavesData = dates.map(date => ({
        date,
        saves: Math.floor(Math.random() * 50) + 5
      }));
      
      // Mock data for tokenized properties
      const mockTokenizedData = dates.map(date => ({
        date,
        tokenized: Math.floor(Math.random() * 20) + 1
      }));
      
      // Mock data for risk grade distribution
      const mockRiskGradeData = [
        { name: 'Green', value: Math.floor(Math.random() * 60) + 20 },
        { name: 'Amber', value: Math.floor(Math.random() * 40) + 10 },
        { name: 'Red', value: Math.floor(Math.random() * 20) + 5 }
      ];
      
      // Mock data for average time on listing
      const mockTimeOnListingData = dates.map(date => ({
        date,
        days: Math.floor(Math.random() * 30) + 5
      }));
      
      // Mock data for inquiry-to-lead conversion
      const mockConversionData = dates.map(date => ({
        date,
        percentage: (Math.random() * 30) + 10
      }));
      
      // Mock data for tokens traded
      const mockTokensTraded = dates.map(date => ({
        date,
        tokens: Math.floor(Math.random() * 1000) + 100
      }));
      
      // Update state with mock data
      setViewsData(mockViewsData);
      setSavesData(mockSavesData);
      setTokenizedData(mockTokenizedData);
      setRiskGradeData(mockRiskGradeData);
      setTimeOnListingData(mockTimeOnListingData);
      setConversionData(mockConversionData);
      setTokensTraded(mockTokensTraded);
      
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching analytics data:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch analytics data. Please try again.',
        variant: 'destructive'
      });
      setIsLoading(false);
    }
  };

  // Generate dates for x-axis based on time filter
  const generateDates = () => {
    const { from, to } = dateRange;
    const dates = [];
    const currentDate = new Date(from);
    
    while (currentDate <= to) {
      let dateStr;
      
      if (timeFilter === 'daily') {
        dateStr = format(currentDate, 'MMM dd');
        currentDate.setDate(currentDate.getDate() + 1);
      } else if (timeFilter === 'weekly') {
        dateStr = `Week ${format(currentDate, 'w')}`;
        currentDate.setDate(currentDate.getDate() + 7);
      } else if (timeFilter === 'monthly') {
        dateStr = format(currentDate, 'MMM yyyy');
        currentDate.setMonth(currentDate.getMonth() + 1);
      }
      
      dates.push(dateStr);
    }
    
    return dates;
  };

  // Export PDF report
  const exportPdfReport = async () => {
    setIsExporting(true);
    
    try {
      // In a real implementation, this would be an API call to generate and download a PDF
      // For this example, we'll simulate a delay and show a success message
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      toast({
        title: 'Success',
        description: 'PDF report has been generated and downloaded.',
        variant: 'default'
      });
      
      setIsExporting(false);
    } catch (error) {
      console.error('Error exporting PDF report:', error);
      toast({
        title: 'Error',
        description: 'Failed to export PDF report. Please try again.',
        variant: 'destructive'
      });
      setIsExporting(false);
    }
  };

  // Schedule weekly email
  const scheduleWeeklyEmail = async () => {
    setIsScheduling(true);
    
    try {
      // In a real implementation, this would be an API call to schedule emails
      // For this example, we'll simulate a delay and show a success message
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      toast({
        title: 'Success',
        description: `Email reports scheduled for ${emailPreferences.frequency} delivery.`,
        variant: 'default'
      });
      
      setIsScheduling(false);
    } catch (error) {
      console.error('Error scheduling email:', error);
      toast({
        title: 'Error',
        description: 'Failed to schedule email reports. Please try again.',
        variant: 'destructive'
      });
      setIsScheduling(false);
    }
  };

  // Handle time filter change
  const handleTimeFilterChange = (value) => {
    setTimeFilter(value);
  };

  // Handle project change
  const handleProjectChange = (value) => {
    setSelectedProject(value);
  };

  // Handle email preference changes
  const handleEmailPreferenceChange = (field, value) => {
    setEmailPreferences(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Handle KPI toggle
  const handleKpiToggle = (kpi) => {
    setEmailPreferences(prev => ({
      ...prev,
      kpis: {
        ...prev.kpis,
        [kpi]: !prev.kpis[kpi]
      }
    }));
  };

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Analytics Dashboard</h1>
      
      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium mb-1">Time Period</label>
          <Select value={timeFilter} onValueChange={handleTimeFilterChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select time period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
            </SelectContent>
          </Select>
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-1">Project</label>
          <Select value={selectedProject} onValueChange={handleProjectChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select project" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Projects</SelectItem>
              {projects.map(project => (
                <SelectItem key={project.id} value={project.id}>
                  {project.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1">Custom Date Range</label>
          <DatePickerWithRange 
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
          />
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex flex-wrap gap-4 mb-6">
        <Button 
          onClick={exportPdfReport} 
          disabled={isExporting || isLoading}
          className="bg-[#1F4AFF] hover:bg-blue-700"
        >
          {isExporting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              Export PDF Report
            </>
          )}
        </Button>
        
        <Button 
          onClick={() => document.getElementById('email-preferences').showModal()}
          variant="outline"
          className="border-[#1F4AFF] text-[#1F4AFF]"
        >
          <Mail className="mr-2 h-4 w-4" />
          Configure Email Reports
        </Button>
      </div>
      
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-[#1F4AFF]" />
          <span className="ml-2">Loading analytics data...</span>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Total Views</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {viewsData.reduce((sum, item) => sum + item.views, 0)}
                </p>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Total Saves</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {savesData.reduce((sum, item) => sum + item.saves, 0)}
                </p>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Tokenized Units</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {tokenizedData.reduce((sum, item) => sum + item.tokenized, 0)}
                </p>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Avg. Conversion</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {(conversionData.reduce((sum, item) => sum + item.percentage, 0) / conversionData.length).toFixed(1)}%
                </p>
              </CardContent>
            </Card>
          </div>
          
          {/* Charts */}
          <Tabs defaultValue="engagement" className="mb-6">
            <TabsList className="mb-4">
              <TabsTrigger value="engagement">Engagement</TabsTrigger>
              <TabsTrigger value="investment">Investment</TabsTrigger>
              <TabsTrigger value="risk">Risk Analysis</TabsTrigger>
            </TabsList>
            
            <TabsContent value="engagement" className="space-y-6">
              {/* Views & Saves Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Views & Saves Over Time</CardTitle>
                  <CardDescription>
                    Track user engagement with your properties
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={viewsData.map((item, index) => ({
                          ...item,
                          saves: savesData[index]?.saves || 0
                        }))}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Line 
                          type="monotone" 
                          dataKey="views" 
                          stroke="#1F4AFF" 
                          activeDot={{ r: 8 }} 
                        />
                        <Line 
                          type="monotone" 
                          dataKey="saves" 
                          stroke="#27AE60" 
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
              
              {/* Time on Listing Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Average Time on Listing (Days)</CardTitle>
                  <CardDescription>
                    How long properties stay listed before being sold
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={timeOnListingData}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar 
                          dataKey="days" 
                          fill="#1F4AFF" 
                          name="Avg. Days on Listing" 
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
              
              {/* Conversion Rate Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Inquiry-to-Lead Conversion Rate (%)</CardTitle>
                  <CardDescription>
                    Percentage of inquiries that convert to qualified leads
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={conversionData}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Line 
                          type="monotone" 
                          dataKey="percentage" 
                          stroke="#9B59B6" 
                          name="Conversion Rate (%)" 
                          activeDot={{ r: 8 }} 
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="investment" className="space-y-6">
              {/* Tokenized Properties Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Tokenized Properties Over Time</CardTitle>
                  <CardDescription>
                    Number of properties tokenized for fractional ownership
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={tokenizedData}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar 
                          dataKey="tokenized" 
                          fill="#1F4AFF" 
                          name="Tokenized Properties" 
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
              
              {/* Tokens Traded Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Tokens Traded (Secondary Liquidity)</CardTitle>
                  <CardDescription>
                    Volume of tokens traded on the secondary marketplace
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={tokensTraded}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Line 
                          type="monotone" 
                          dataKey="tokens" 
                          stroke="#27AE60" 
                          name="Tokens Traded" 
                          activeDot={{ r: 8 }} 
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="risk" className="space-y-6">
              {/* Risk Grade Distribution Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>Risk Grade Distribution</CardTitle>
                  <CardDescription>
                    Breakdown of properties by risk grade
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={riskGradeData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {riskGradeData.map((entry, index) => (
                            <Cell 
                              key={`cell-${index}`} 
                              fill={RISK_COLORS[entry.name]} 
                            />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
              
              {/* Heat Map */}
              <Card>
                <CardHeader>
                  <CardTitle>Risk Grade Heat Map by Tower & Floor</CardTitle>
                  <CardDescription>
                    Visual representation of risk grades across properties
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-96">
                    <HeatMapChart />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
      
      {/* Email Preferences Modal */}
      <dialog id="email-preferences" className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg mb-4">Email Report Preferences</h3>
          
          <div className="space-y-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="email-enabled"
                checked={emailPreferences.enabled}
                onChange={(e) => handleEmailPreferenceChange('enabled', e.target.checked)}
                className="mr-2"
              />
              <label htmlFor="email-enabled">Enable scheduled email reports</label>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">Frequency</label>
              <Select 
                value={emailPreferences.frequency} 
                onValueChange={(value) => handleEmailPreferenceChange('frequency', value)}
                disabled={!emailPreferences.enabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select frequency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="bi-weekly">Bi-Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">Day</label>
              <Select 
                value={emailPreferences.day} 
                onValueChange={(value) => handleEmailPreferenceChange('day', value)}
                disabled={!emailPreferences.enabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select day" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monday">Monday</SelectItem>
                  <SelectItem value="tuesday">Tuesday</SelectItem>
                  <SelectItem value="wednesday">Wednesday</SelectItem>
                  <SelectItem value="thursday">Thursday</SelectItem>
                  <SelectItem value="friday">Friday</SelectItem>
                  <SelectItem value="saturday">Saturday</SelectItem>
                  <SelectItem value="sunday">Sunday</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-1">Time (GST)</label>
              <Select 
                value={emailPreferences.time} 
                onValueChange={(value) => handleEmailPreferenceChange('time', value)}
                disabled={!emailPreferences.enabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select time" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="08:00">08:00 AM</SelectItem>
                  <SelectItem value="12:00">12:00 PM</SelectItem>
                  <SelectItem value="16:00">04:00 PM</SelectItem>
                  <SelectItem value="20:00">08:00 PM</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Include KPIs:</h4>
              <div className="space-y-2">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-views"
                    checked={emailPreferences.kpis.views}
                    onChange={() => handleKpiToggle('views')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-views">Views</label>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-saves"
                    checked={emailPreferences.kpis.saves}
                    onChange={() => handleKpiToggle('saves')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-saves">Saves</label>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-tokenized"
                    checked={emailPreferences.kpis.tokenized}
                    onChange={() => handleKpiToggle('tokenized')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-tokenized">Tokenized</label>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-riskGrade"
                    checked={emailPreferences.kpis.riskGrade}
                    onChange={() => handleKpiToggle('riskGrade')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-riskGrade">Risk Grade Mix</label>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-timeOnListing"
                    checked={emailPreferences.kpis.timeOnListing}
                    onChange={() => handleKpiToggle('timeOnListing')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-timeOnListing">Time on Listing</label>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-conversion"
                    checked={emailPreferences.kpis.conversion}
                    onChange={() => handleKpiToggle('conversion')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-conversion">Conversion Rate</label>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="kpi-tokensTraded"
                    checked={emailPreferences.kpis.tokensTraded}
                    onChange={() => handleKpiToggle('tokensTraded')}
                    disabled={!emailPreferences.enabled}
                    className="mr-2"
                  />
                  <label htmlFor="kpi-tokensTraded">Tokens Traded</label>
                </div>
              </div>
            </div>
          </div>
          
          <div className="modal-action">
            <form method="dialog">
              <Button 
                type="button" 
                onClick={scheduleWeeklyEmail}
                disabled={isScheduling || !emailPreferences.enabled}
                className="mr-2 bg-[#1F4AFF] hover:bg-blue-700"
              >
                {isScheduling ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    Save Preferences
                  </>
                )}
              </Button>
              <Button type="submit" variant="outline">Close</Button>
            </form>
          </div>
        </div>
      </dialog>
    </div>
  );
};

export default Analytics;
