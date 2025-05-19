import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { useTranslation } from 'next-i18next';
import { 
  Box, 
  Tabs, 
  TabList, 
  Tab, 
  TabPanels, 
  TabPanel, 
  Heading, 
  Text, 
  Flex, 
  Button, 
  Progress, 
  Badge, 
  Card, 
  CardHeader, 
  CardBody, 
  Stack, 
  StackDivider,
  Grid,
  GridItem,
  Divider,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Input,
  FormControl,
  FormLabel,
  Switch
} from '@chakra-ui/react';
import { 
  CheckCircleIcon, 
  WarningIcon, 
  TimeIcon, 
  InfoIcon, 
  ExternalLinkIcon,
  CopyIcon,
  LinkIcon
} from '@chakra-ui/icons';
import { ethers } from 'ethers';
import QRCode from 'react-qr-code';

import DashboardLayout from '../layouts/DashboardLayout';

const SyndicateTab = () => {
  const { t } = useTranslation('common');
  const router = useRouter();
  const toast = useToast();
  
  // State for syndicate data
  const [syndicateData, setSyndicateData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [walletConnected, setWalletConnected] = useState(false);
  const [walletAddress, setWalletAddress] = useState('');
  const [fundingProgress, setFundingProgress] = useState(0);
  const [kycStatus, setKycStatus] = useState('pending');
  const [signStatus, setSignStatus] = useState('pending');
  const [tokenStatus, setTokenStatus] = useState('not_minted');
  
  // Modal states
  const { isOpen: isWalletOpen, onOpen: onWalletOpen, onClose: onWalletClose } = useDisclosure();
  const { isOpen: isKycOpen, onOpen: onKycOpen, onClose: onKycClose } = useDisclosure();
  const { isOpen: isReinvestOpen, onOpen: onReinvestOpen, onClose: onReinvestClose } = useDisclosure();
  
  // Form state
  const [autoReinvest, setAutoReinvest] = useState(false);
  
  // Mock data for development
  const mockSyndicateData = {
    id: 1,
    name: 'UNO-611 Syndicate',
    property: {
      id: 'UNO-611',
      name: 'UNO Luxury Apartment 611',
      project: 'Al Marjan Island, RAK',
      image: 'https://example.com/property.jpg',
      price: 1117105,
      size: 950,
      view: 'Sea View',
      developer: 'Emaar Properties'
    },
    target_raise: 1117105,
    current_raise: 670263,
    min_investment: 50000,
    investors_count: 7,
    max_investors: 10,
    token_address: '0x1234567890123456789012345678901234567890',
    token_name: 'PropPulse UNO-611',
    token_symbol: 'PPUNO611',
    status: 'funding', // funding, completed, failed
    deadline: '2025-06-30T00:00:00Z',
    documents: [
      { id: 1, name: 'Syndicate Agreement', status: 'pending', url: '#' },
      { id: 2, name: 'Sale and Purchase Agreement', status: 'pending', url: '#' }
    ],
    roi: {
      net_yield: 9.8,
      irr_10yr: 14.6,
      adr: 850,
      occupancy: 85,
      gross_rental_income: 264112,
      service_charge: 15.5,
      net_income: 109312,
      capital_appreciation: 7.0
    }
  };
  
  // Fetch syndicate data
  useEffect(() => {
    // In a real app, fetch from API
    setTimeout(() => {
      setSyndicateData(mockSyndicateData);
      setFundingProgress(Math.round((mockSyndicateData.current_raise / mockSyndicateData.target_raise) * 100));
      setLoading(false);
    }, 1000);
  }, []);
  
  // Connect wallet function
  const connectWallet = async () => {
    if (window.ethereum) {
      try {
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        setWalletAddress(accounts[0]);
        setWalletConnected(true);
        
        toast({
          title: 'Wallet Connected',
          description: `Connected to ${accounts[0].substring(0, 6)}...${accounts[0].substring(38)}`,
          status: 'success',
          duration: 5000,
          isClosable: true,
        });
        
        onWalletClose();
      } catch (error) {
        console.error('Error connecting wallet:', error);
        toast({
          title: 'Connection Failed',
          description: error.message,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } else {
      toast({
        title: 'Metamask Not Found',
        description: 'Please install Metamask to connect your wallet',
        status: 'warning',
        duration: 5000,
        isClosable: true,
      });
    }
  };
  
  // Start KYC process
  const startKyc = () => {
    // In a real app, redirect to IDnow or open iframe
    setKycStatus('in_progress');
    toast({
      title: 'KYC Started',
      description: 'You will be redirected to our KYC provider',
      status: 'info',
      duration: 5000,
      isClosable: true,
    });
    
    // Mock KYC completion after 3 seconds
    setTimeout(() => {
      setKycStatus('approved');
      toast({
        title: 'KYC Completed',
        description: 'Your identity has been verified successfully',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
      onKycClose();
    }, 3000);
  };
  
  // Sign documents
  const signDocuments = () => {
    // In a real app, redirect to Zoho Sign or open iframe
    setSignStatus('in_progress');
    toast({
      title: 'Signing Process Started',
      description: 'You will be redirected to our document signing provider',
      status: 'info',
      duration: 5000,
      isClosable: true,
    });
    
    // Mock signing completion after 3 seconds
    setTimeout(() => {
      setSignStatus('signed');
      toast({
        title: 'Documents Signed',
        description: 'All required documents have been signed successfully',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
    }, 3000);
  };
  
  // Update auto-reinvest preference
  const updateReinvestPreference = () => {
    // In a real app, send to API
    toast({
      title: 'Preference Updated',
      description: `Auto-reinvest has been ${autoReinvest ? 'enabled' : 'disabled'}`,
      status: 'success',
      duration: 5000,
      isClosable: true,
    });
    onReinvestClose();
  };
  
  // Copy to clipboard helper
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast({
      title: 'Copied to Clipboard',
      description: 'The text has been copied to your clipboard',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };
  
  // Render loading state
  if (loading) {
    return (
      <Flex justify="center" align="center" h="50vh" direction="column">
        <Progress size="xs" isIndeterminate w="200px" />
        <Text mt={4}>Loading syndicate data...</Text>
      </Flex>
    );
  }
  
  // Render syndicate dashboard
  return (
    <Box>
      <Heading size="lg" mb={6}>
        {syndicateData.name}
      </Heading>
      
      {/* Property Overview Card */}
      <Card mb={6}>
        <CardHeader>
          <Heading size="md">Property Overview</Heading>
        </CardHeader>
        <CardBody>
          <Grid templateColumns="repeat(2, 1fr)" gap={4}>
            <GridItem>
              <Text fontWeight="bold">Property ID:</Text>
              <Text>{syndicateData.property.id}</Text>
              
              <Text fontWeight="bold" mt={2}>Location:</Text>
              <Text>{syndicateData.property.project}</Text>
              
              <Text fontWeight="bold" mt={2}>Size:</Text>
              <Text>{syndicateData.property.size} ft²</Text>
              
              <Text fontWeight="bold" mt={2}>View:</Text>
              <Text>{syndicateData.property.view}</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">Purchase Price:</Text>
              <Text>AED {syndicateData.property.price.toLocaleString()}</Text>
              
              <Text fontWeight="bold" mt={2}>Developer:</Text>
              <Text>{syndicateData.property.developer}</Text>
              
              <Text fontWeight="bold" mt={2}>Net Yield:</Text>
              <Text>{syndicateData.roi.net_yield}%</Text>
              
              <Text fontWeight="bold" mt={2}>10-Year IRR:</Text>
              <Text>{syndicateData.roi.irr_10yr}%</Text>
            </GridItem>
          </Grid>
        </CardBody>
      </Card>
      
      {/* Funding Progress Card */}
      <Card mb={6}>
        <CardHeader>
          <Heading size="md">Funding Progress</Heading>
        </CardHeader>
        <CardBody>
          <Text mb={2}>
            AED {syndicateData.current_raise.toLocaleString()} of AED {syndicateData.target_raise.toLocaleString()} raised
          </Text>
          <Progress value={fundingProgress} colorScheme="green" size="lg" borderRadius="md" mb={4} />
          <Flex justify="space-between" align="center">
            <Text>{fundingProgress}% Complete</Text>
            <Text>{syndicateData.investors_count} of {syndicateData.max_investors} investors</Text>
          </Flex>
          <Flex mt={4} justify="space-between" align="center">
            <Text>Minimum Investment: AED {syndicateData.min_investment.toLocaleString()}</Text>
            <Text>Deadline: {new Date(syndicateData.deadline).toLocaleDateString()}</Text>
          </Flex>
        </CardBody>
      </Card>
      
      {/* Investor Onboarding Card */}
      <Card mb={6}>
        <CardHeader>
          <Heading size="md">Investor Onboarding</Heading>
        </CardHeader>
        <CardBody>
          <Stack divider={<StackDivider />} spacing={4}>
            {/* Wallet Connection */}
            <Flex justify="space-between" align="center">
              <Box>
                <Flex align="center">
                  {walletConnected ? (
                    <CheckCircleIcon color="green.500" mr={2} />
                  ) : (
                    <WarningIcon color="orange.500" mr={2} />
                  )}
                  <Text fontWeight="bold">Connect Wallet</Text>
                </Flex>
                {walletConnected && (
                  <Text fontSize="sm" color="gray.600" mt={1}>
                    {walletAddress.substring(0, 6)}...{walletAddress.substring(38)}
                    <CopyIcon 
                      ml={2} 
                      cursor="pointer" 
                      onClick={() => copyToClipboard(walletAddress)}
                    />
                  </Text>
                )}
              </Box>
              <Button 
                colorScheme={walletConnected ? "gray" : "blue"} 
                size="sm"
                onClick={onWalletOpen}
              >
                {walletConnected ? "Change Wallet" : "Connect Wallet"}
              </Button>
            </Flex>
            
            {/* KYC Verification */}
            <Flex justify="space-between" align="center">
              <Box>
                <Flex align="center">
                  {kycStatus === 'approved' ? (
                    <CheckCircleIcon color="green.500" mr={2} />
                  ) : kycStatus === 'in_progress' ? (
                    <TimeIcon color="blue.500" mr={2} />
                  ) : (
                    <WarningIcon color="orange.500" mr={2} />
                  )}
                  <Text fontWeight="bold">KYC Verification</Text>
                </Flex>
                <Text fontSize="sm" color="gray.600" mt={1}>
                  {kycStatus === 'approved' 
                    ? 'Verified on ' + new Date().toLocaleDateString() 
                    : kycStatus === 'in_progress'
                    ? 'Verification in progress'
                    : 'Identity verification required'}
                </Text>
              </Box>
              <Button 
                colorScheme={kycStatus === 'approved' ? "green" : "blue"} 
                size="sm"
                isDisabled={kycStatus === 'approved' || !walletConnected}
                onClick={onKycOpen}
              >
                {kycStatus === 'approved' ? "Verified" : "Start KYC"}
              </Button>
            </Flex>
            
            {/* Document Signing */}
            <Flex justify="space-between" align="center">
              <Box>
                <Flex align="center">
                  {signStatus === 'signed' ? (
                    <CheckCircleIcon color="green.500" mr={2} />
                  ) : signStatus === 'in_progress' ? (
                    <TimeIcon color="blue.500" mr={2} />
                  ) : (
                    <WarningIcon color="orange.500" mr={2} />
                  )}
                  <Text fontWeight="bold">Document Signing</Text>
                </Flex>
                <Text fontSize="sm" color="gray.600" mt={1}>
                  {signStatus === 'signed' 
                    ? 'All documents signed' 
                    : signStatus === 'in_progress'
                    ? 'Signing in progress'
                    : 'Syndicate Agreement and SPA require signature'}
                </Text>
              </Box>
              <Button 
                colorScheme={signStatus === 'signed' ? "green" : "blue"} 
                size="sm"
                isDisabled={signStatus === 'signed' || kycStatus !== 'approved'}
                onClick={signDocuments}
              >
                {signStatus === 'signed' ? "Signed" : "Sign Documents"}
              </Button>
            </Flex>
            
            {/* Token Status */}
            <Flex justify="space-between" align="center">
              <Box>
                <Flex align="center">
                  {tokenStatus === 'minted' ? (
                    <CheckCircleIcon color="green.500" mr={2} />
                  ) : tokenStatus === 'minting' ? (
                    <TimeIcon color="blue.500" mr={2} />
                  ) : (
                    <InfoIcon color="gray.500" mr={2} />
                  )}
                  <Text fontWeight="bold">Token Status</Text>
                </Flex>
                <Text fontSize="sm" color="gray.600" mt={1}>
                  {tokenStatus === 'minted' 
                    ? 'Tokens minted to your wallet' 
                    : tokenStatus === 'minting'
                    ? 'Token minting in progress'
                    : 'Tokens will be minted after signing and funding'}
                </Text>
              </Box>
              {tokenStatus === 'minted' ? (
                <Button 
                  colorScheme="purple" 
                  size="sm"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() => window.open(`https://polygonscan.com/token/${syndicateData.token_address}`, '_blank')}
                >
                  View on Polygonscan
                </Button>
              ) : (
                <Badge colorScheme={tokenStatus === 'minting' ? "blue" : "gray"}>
                  {tokenStatus === 'minting' ? "Processing" : "Pending"}
                </Badge>
              )}
            </Flex>
          </Stack>
        </CardBody>
      </Card>
      
      {/* Investment Details Card */}
      <Card mb={6}>
        <CardHeader>
          <Heading size="md">Investment Details</Heading>
        </CardHeader>
        <CardBody>
          <Grid templateColumns="repeat(2, 1fr)" gap={6}>
            <GridItem>
              <Text fontWeight="bold">Token Contract:</Text>
              <Flex align="center" mt={1}>
                <Text fontSize="sm" isTruncated maxW="200px">
                  {syndicateData.token_address}
                </Text>
                <CopyIcon 
                  ml={2} 
                  cursor="pointer" 
                  onClick={() => copyToClipboard(syndicateData.token_address)}
                />
                <ExternalLinkIcon 
                  ml={2} 
                  cursor="pointer" 
                  onClick={() => window.open(`https://polygonscan.com/token/${syndicateData.token_address}`, '_blank')}
                />
              </Flex>
              
              <Text fontWeight="bold" mt={4}>Token Name:</Text>
              <Text>{syndicateData.token_name}</Text>
              
              <Text fontWeight="bold" mt={4}>Token Symbol:</Text>
              <Text>{syndicateData.token_symbol}</Text>
            </GridItem>
            
            <GridItem>
              <Text fontWeight="bold">Auto-Reinvest:</Text>
              <Flex align="center" mt={1}>
                <Text mr={4}>{autoReinvest ? "Enabled" : "Disabled"}</Text>
                <Button 
                  size="xs" 
                  colorScheme="blue"
                  onClick={onReinvestOpen}
                >
                  Change
                </Button>
              </Flex>
              
              <Text fontWeight="bold" mt={4}>Next Distribution:</Text>
              <Text>5th of next month</Text>
              
              <Text fontWeight="bold" mt={4}>Documents:</Text>
              <Stack mt={1} spacing={1}>
                {syndicateData.documents.map(doc => (
                  <Flex key={doc.id} align="center">
                    <LinkIcon mr={2} />
                    <Text 
                      color="blue.500" 
                      cursor="pointer"
                      onClick={() => window.open(doc.url, '_blank')}
                    >
                      {doc.name}
                    </Text>
                    <Badge ml={2} colorScheme={
                      doc.status === 'signed' ? 'green' : 
                      doc.status === 'pending' ? 'yellow' : 'red'
                    }>
                      {doc.status}
                    </Badge>
                  </Flex>
                ))}
              </Stack>
            </GridItem>
          </Grid>
        </CardBody>
      </Card>
      
      {/* ROI Details Card */}
      <Card mb={6}>
        <CardHeader>
          <Heading size="md">ROI Details</Heading>
        </CardHeader>
        <CardBody>
          <Grid templateColumns="repeat(4, 1fr)" gap={4}>
            <GridItem>
              <Text fontWeight="bold">Net Yield:</Text>
              <Text fontSize="xl" color="green.500">{syndicateData.roi.net_yield}%</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">10-Year IRR:</Text>
              <Text fontSize="xl" color="green.500">{syndicateData.roi.irr_10yr}%</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">ADR:</Text>
              <Text>AED {syndicateData.roi.adr}</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">Occupancy:</Text>
              <Text>{syndicateData.roi.occupancy}%</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">Gross Rental Income:</Text>
              <Text>AED {syndicateData.roi.gross_rental_income.toLocaleString()}</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">Service Charge:</Text>
              <Text>AED {syndicateData.roi.service_charge}/ft²</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">Net Income:</Text>
              <Text>AED {syndicateData.roi.net_income.toLocaleString()}</Text>
            </GridItem>
            <GridItem>
              <Text fontWeight="bold">Capital Appreciation:</Text>
              <Text>{syndicateData.roi.capital_appreciation}% CAGR</Text>
            </GridItem>
          </Grid>
        </CardBody>
      </Card>
      
      {/* Wallet Connection Modal */}
      <Modal isOpen={isWalletOpen} onClose={onWalletClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Connect Wallet</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text mb={4}>
              Connect your wallet to participate in this syndicate. We support Metamask and other Ethereum-compatible wallets.
            </Text>
            <Flex direction="column" align="center" justify="center" py={4}>
              <Box 
                p={4} 
                borderWidth={1} 
                borderRadius="md" 
                cursor="pointer" 
                _hover={{ bg: 'gray.50' }}
                onClick={connectWallet}
                mb={4}
                w="100%"
              >
                <Flex align="center" justify="center">
                  <img src="/metamask-logo.svg" alt="Metamask" width="30" height="30" />
                  <Text ml={3} fontWeight="bold">Metamask</Text>
                </Flex>
              </Box>
              <Box 
                p={4} 
                borderWidth={1} 
                borderRadius="md" 
                cursor="pointer" 
                _hover={{ bg: 'gray.50' }}
                onClick={connectWallet}
                w="100%"
              >
                <Flex align="center" justify="center">
                  <img src="/walletconnect-logo.svg" alt="WalletConnect" width="30" height="30" />
                  <Text ml={3} fontWeight="bold">WalletConnect</Text>
                </Flex>
              </Box>
            </Flex>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={onWalletClose}>Cancel</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      
      {/* KYC Modal */}
      <Modal isOpen={isKycOpen} onClose={onKycClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>KYC Verification</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text mb={4}>
              Complete the KYC verification process to participate in this syndicate. This is required by UAE regulations.
            </Text>
            <Box p={4} borderWidth={1} borderRadius="md" mb={4}>
              <Text fontWeight="bold" mb={2}>What you'll need:</Text>
              <Text>• Valid government-issued ID (passport preferred)</Text>
              <Text>• Proof of address (utility bill, bank statement)</Text>
              <Text>• Webcam for video verification</Text>
              <Text>• Approximately 5-10 minutes of your time</Text>
            </Box>
            <Box p={4} borderWidth={1} borderRadius="md" bg="blue.50">
              <Text fontWeight="bold" mb={2}>Privacy Notice:</Text>
              <Text fontSize="sm">
                Your personal information will be processed in accordance with UAE ESCA/SCA regulations and EU GDPR. 
                We use IDnow as our KYC provider, which maintains the highest security standards.
              </Text>
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onKycClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={startKyc}>Start Verification</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      
      {/* Auto-Reinvest Modal */}
      <Modal isOpen={isReinvestOpen} onClose={onReinvestClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Auto-Reinvest Settings</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text mb={4}>
              When enabled, your rental income will be automatically reinvested into new PropPulse properties instead of being distributed to your wallet.
            </Text>
            <FormControl display="flex" alignItems="center" mb={4}>
              <FormLabel htmlFor="auto-reinvest" mb="0">
                Enable Auto-Reinvest
              </FormLabel>
              <Switch 
                id="auto-reinvest" 
                isChecked={autoReinvest}
                onChange={(e) => setAutoReinvest(e.target.checked)}
              />
            </FormControl>
            <Box p={4} borderWidth={1} borderRadius="md" bg="gray.50">
              <Text fontSize="sm">
                Note: You can change this setting at any time. The minimum distribution amount is AED 200. Amounts below this threshold will be rolled forward regardless of this setting.
              </Text>
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onReinvestClose}>Cancel</Button>
            <Button colorScheme="blue" onClick={updateReinvestPreference}>Save Preference</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

const InvestorDashboard = () => {
  const { t } = useTranslation('common');
  
  return (
    <DashboardLayout>
      <Box p={6}>
        <Tabs colorScheme="blue" variant="enclosed">
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Properties</Tab>
            <Tab>Syndicate</Tab>
            <Tab>Marketplace</Tab>
            <Tab>Settings</Tab>
          </TabList>
          
          <TabPanels>
            <TabPanel>
              <Heading size="lg" mb={6}>Investor Dashboard</Heading>
              <Text>Welcome to your PropPulse investor dashboard.</Text>
            </TabPanel>
            
            <TabPanel>
              <Heading size="lg" mb={6}>Properties</Heading>
              <Text>View all available properties.</Text>
            </TabPanel>
            
            <TabPanel>
              <SyndicateTab />
            </TabPanel>
            
            <TabPanel>
              <Heading size="lg" mb={6}>Marketplace</Heading>
              <Text>Buy and sell property tokens on the secondary market.</Text>
            </TabPanel>
            
            <TabPanel>
              <Heading size="lg" mb={6}>Settings</Heading>
              <Text>Manage your account settings.</Text>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </Box>
    </DashboardLayout>
  );
};

export default InvestorDashboard;

export async function getServerSideProps({ locale }) {
  return {
    props: {
      ...(await serverSideTranslations(locale, ['common'])),
    },
  };
}
