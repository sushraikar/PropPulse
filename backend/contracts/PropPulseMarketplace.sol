// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC1400/IERC1400.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title PropPulseMarketplace
 * @dev Secondary marketplace for PropPulse ERC-1400 security tokens
 * Features:
 * - Simple AMM for token swaps
 * - Configurable seller fee
 * - Whitelist-based access control
 * - Compliance checks and reporting
 */
contract PropPulseMarketplace is Ownable, ReentrancyGuard {
    // Fee configuration
    uint256 public sellerFeePercentage = 400; // 4% by default (in basis points)
    address public feeCollector;
    
    // Whitelist registry
    mapping(address => bool) public whitelistedAddresses;
    
    // Token registry
    mapping(address => bool) public supportedTokens;
    
    // Trade limits
    uint256 public maxTradeValueAED = 500000 * 1e18; // 500,000 AED in wei
    
    // Events
    event TokenSwapped(
        address indexed token,
        address indexed seller,
        address indexed buyer,
        uint256 amount,
        uint256 price,
        uint256 fee,
        bytes32 partition
    );
    
    event WhitelistUpdated(address indexed account, bool status);
    event TokenSupportUpdated(address indexed token, bool supported);
    event FeeUpdated(uint256 newFeePercentage);
    event FeeCollectorUpdated(address indexed newFeeCollector);
    event MaxTradeValueUpdated(uint256 newMaxTradeValue);
    
    // Compliance reporting
    event ComplianceReport(
        address indexed token,
        address indexed seller,
        address indexed buyer,
        uint256 amount,
        uint256 price,
        uint256 timestamp,
        bytes32 tradeId
    );
    
    /**
     * @dev Constructor
     * @param _feeCollector Address to collect fees
     */
    constructor(address _feeCollector) {
        require(_feeCollector != address(0), "Fee collector cannot be zero address");
        feeCollector = _feeCollector;
    }
    
    /**
     * @dev Set seller fee percentage
     * @param _feePercentage New fee percentage in basis points (e.g., 400 = 4%)
     */
    function setSellerFeePercentage(uint256 _feePercentage) external onlyOwner {
        require(_feePercentage <= 1000, "Fee cannot exceed 10%");
        sellerFeePercentage = _feePercentage;
        emit FeeUpdated(_feePercentage);
    }
    
    /**
     * @dev Set fee collector address
     * @param _feeCollector New fee collector address
     */
    function setFeeCollector(address _feeCollector) external onlyOwner {
        require(_feeCollector != address(0), "Fee collector cannot be zero address");
        feeCollector = _feeCollector;
        emit FeeCollectorUpdated(_feeCollector);
    }
    
    /**
     * @dev Set maximum trade value in AED
     * @param _maxTradeValueAED New maximum trade value in AED (in wei)
     */
    function setMaxTradeValueAED(uint256 _maxTradeValueAED) external onlyOwner {
        maxTradeValueAED = _maxTradeValueAED;
        emit MaxTradeValueUpdated(_maxTradeValueAED);
    }
    
    /**
     * @dev Add or remove address from whitelist
     * @param _account Address to update
     * @param _status Whitelist status
     */
    function updateWhitelist(address _account, bool _status) external onlyOwner {
        whitelistedAddresses[_account] = _status;
        emit WhitelistUpdated(_account, _status);
    }
    
    /**
     * @dev Batch update whitelist
     * @param _accounts Addresses to update
     * @param _statuses Whitelist statuses
     */
    function batchUpdateWhitelist(address[] calldata _accounts, bool[] calldata _statuses) external onlyOwner {
        require(_accounts.length == _statuses.length, "Arrays length mismatch");
        
        for (uint256 i = 0; i < _accounts.length; i++) {
            whitelistedAddresses[_accounts[i]] = _statuses[i];
            emit WhitelistUpdated(_accounts[i], _statuses[i]);
        }
    }
    
    /**
     * @dev Add or remove token from supported tokens
     * @param _token Token address
     * @param _supported Support status
     */
    function updateTokenSupport(address _token, bool _supported) external onlyOwner {
        supportedTokens[_token] = _supported;
        emit TokenSupportUpdated(_token, _supported);
    }
    
    /**
     * @dev Batch update token support
     * @param _tokens Token addresses
     * @param _supported Support statuses
     */
    function batchUpdateTokenSupport(address[] calldata _tokens, bool[] calldata _supported) external onlyOwner {
        require(_tokens.length == _supported.length, "Arrays length mismatch");
        
        for (uint256 i = 0; i < _tokens.length; i++) {
            supportedTokens[_tokens[i]] = _supported[i];
            emit TokenSupportUpdated(_tokens[i], _supported[i]);
        }
    }
    
    /**
     * @dev Swap tokens between seller and buyer
     * @param _token ERC-1400 token address
     * @param _partition Token partition
     * @param _amount Amount of tokens to swap
     * @param _pricePerToken Price per token in wei
     * @param _paymentToken ERC-20 token used for payment (address(0) for ETH)
     */
    function swap(
        address _token,
        bytes32 _partition,
        uint256 _amount,
        uint256 _pricePerToken,
        address _paymentToken
    ) external payable nonReentrant {
        // Check token support
        require(supportedTokens[_token], "Token not supported");
        
        // Check whitelist for buyer
        require(whitelistedAddresses[msg.sender], "Buyer not whitelisted");
        
        // Get seller from token approval
        address seller = IERC1400(_token).isOperator(address(this), msg.sender) ? msg.sender : address(0);
        require(seller != address(0), "Seller not found or not approved");
        
        // Check whitelist for seller
        require(whitelistedAddresses[seller], "Seller not whitelisted");
        
        // Calculate total price and fee
        uint256 totalPrice = _amount * _pricePerToken;
        uint256 fee = (totalPrice * sellerFeePercentage) / 10000;
        uint256 sellerAmount = totalPrice - fee;
        
        // Check trade value limit
        require(totalPrice <= maxTradeValueAED, "Trade value exceeds limit");
        
        // Handle payment
        if (_paymentToken == address(0)) {
            // Payment in ETH
            require(msg.value == totalPrice, "Incorrect ETH amount");
            
            // Transfer fee to fee collector
            (bool feeSuccess, ) = feeCollector.call{value: fee}("");
            require(feeSuccess, "Fee transfer failed");
            
            // Transfer payment to seller
            (bool sellerSuccess, ) = seller.call{value: sellerAmount}("");
            require(sellerSuccess, "Seller payment failed");
        } else {
            // Payment in ERC-20 token
            require(msg.value == 0, "ETH not accepted with token payment");
            
            // Transfer tokens from buyer to fee collector and seller
            require(IERC20(_paymentToken).transferFrom(msg.sender, feeCollector, fee), "Fee transfer failed");
            require(IERC20(_paymentToken).transferFrom(msg.sender, seller, sellerAmount), "Seller payment failed");
        }
        
        // Transfer tokens from seller to buyer
        IERC1400(_token).operatorTransferByPartition(
            _partition,
            seller,
            msg.sender,
            _amount,
            bytes(""),
            bytes("")
        );
        
        // Generate trade ID for compliance reporting
        bytes32 tradeId = keccak256(abi.encodePacked(
            _token,
            seller,
            msg.sender,
            _amount,
            totalPrice,
            block.timestamp
        ));
        
        // Emit events
        emit TokenSwapped(_token, seller, msg.sender, _amount, totalPrice, fee, _partition);
        emit ComplianceReport(_token, seller, msg.sender, _amount, totalPrice, block.timestamp, tradeId);
    }
    
    /**
     * @dev Check if an address is whitelisted
     * @param _account Address to check
     * @return bool Whitelist status
     */
    function isWhitelisted(address _account) external view returns (bool) {
        return whitelistedAddresses[_account];
    }
    
    /**
     * @dev Check if a token is supported
     * @param _token Token address to check
     * @return bool Support status
     */
    function isTokenSupported(address _token) external view returns (bool) {
        return supportedTokens[_token];
    }
    
    /**
     * @dev Calculate fee for a given amount
     * @param _amount Amount to calculate fee for
     * @return uint256 Fee amount
     */
    function calculateFee(uint256 _amount) external view returns (uint256) {
        return (_amount * sellerFeePercentage) / 10000;
    }
}
