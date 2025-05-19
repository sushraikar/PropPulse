// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts-upgradeable/token/ERC1400/ERC1400Upgradeable.sol";
import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/cryptography/EIP712Upgradeable.sol";

/**
 * @title PropPulseToken
 * @dev ERC1400 token for PropPulse real estate tokenization
 * 
 * Features:
 * - Upgradeable via Transparent Proxy pattern
 * - Partitioned tranches (CLASS_A, CLASS_B)
 * - Transfer restrictions for whitelisted addresses
 * - Controller transfer for regulatory compliance
 * - EIP-712 typed-data signatures for gas-less operations
 */
contract PropPulseToken is 
    Initializable, 
    ERC1400Upgradeable, 
    OwnableUpgradeable, 
    PausableUpgradeable,
    EIP712Upgradeable,
    UUPSUpgradeable 
{
    // Property metadata
    string public propertyId;
    string public unitNo;
    string public projectName;
    uint256 public propertyValue;
    
    // Whitelist for transfers
    mapping(address => bool) public whitelist;
    
    // Partition constants
    bytes32 public constant PARTITION_CLASS_A = keccak256("CLASS_A");
    bytes32 public constant PARTITION_CLASS_B = keccak256("CLASS_B");
    
    // Controller address for forced transfers
    address public controller;
    
    // Events
    event AddedToWhitelist(address indexed account);
    event RemovedFromWhitelist(address indexed account);
    event ControllerTransfer(
        address indexed controller,
        address indexed from,
        address indexed to,
        uint256 value,
        bytes data,
        bytes operatorData
    );
    event ControllerRedemption(
        address indexed controller,
        address indexed tokenHolder,
        uint256 value,
        bytes data,
        bytes operatorData
    );
    event PropertyMetadataUpdated(
        string propertyId,
        string unitNo,
        string projectName,
        uint256 propertyValue
    );
    
    // Modifiers
    modifier onlyController() {
        require(msg.sender == controller, "PropPulseToken: caller is not the controller");
        _;
    }
    
    /**
     * @dev Initializes the contract with property metadata and default partitions
     */
    function initialize(
        string memory name,
        string memory symbol,
        address owner,
        address controllerAddress,
        string memory _propertyId,
        string memory _unitNo,
        string memory _projectName,
        uint256 _propertyValue
    ) public initializer {
        __ERC1400_init(name, symbol, 1, new address[](0), new bytes32[](0));
        __Ownable_init(owner);
        __Pausable_init();
        __EIP712_init("PropPulseToken", "1");
        __UUPSUpgradeable_init();
        
        // Set property metadata
        propertyId = _propertyId;
        unitNo = _unitNo;
        projectName = _projectName;
        propertyValue = _propertyValue;
        
        // Set controller
        controller = controllerAddress;
        
        // Set up default partitions
        _setDefaultPartitions([PARTITION_CLASS_A, PARTITION_CLASS_B]);
        
        // Add owner and controller to whitelist
        whitelist[owner] = true;
        whitelist[controller] = true;
    }
    
    /**
     * @dev Add an account to the whitelist
     * @param account Address to add to the whitelist
     */
    function addToWhitelist(address account) external onlyOwner {
        whitelist[account] = true;
        emit AddedToWhitelist(account);
    }
    
    /**
     * @dev Remove an account from the whitelist
     * @param account Address to remove from the whitelist
     */
    function removeFromWhitelist(address account) external onlyOwner {
        whitelist[account] = false;
        emit RemovedFromWhitelist(account);
    }
    
    /**
     * @dev Batch add accounts to the whitelist
     * @param accounts Addresses to add to the whitelist
     */
    function batchAddToWhitelist(address[] calldata accounts) external onlyOwner {
        for (uint256 i = 0; i < accounts.length; i++) {
            whitelist[accounts[i]] = true;
            emit AddedToWhitelist(accounts[i]);
        }
    }
    
    /**
     * @dev Update property metadata
     * @param _propertyId Property ID
     * @param _unitNo Unit number
     * @param _projectName Project name
     * @param _propertyValue Property value in AED
     */
    function updatePropertyMetadata(
        string calldata _propertyId,
        string calldata _unitNo,
        string calldata _projectName,
        uint256 _propertyValue
    ) external onlyOwner {
        propertyId = _propertyId;
        unitNo = _unitNo;
        projectName = _projectName;
        propertyValue = _propertyValue;
        
        emit PropertyMetadataUpdated(_propertyId, _unitNo, _projectName, _propertyValue);
    }
    
    /**
     * @dev Set the controller address
     * @param newController New controller address
     */
    function setController(address newController) external onlyOwner {
        require(newController != address(0), "PropPulseToken: new controller is the zero address");
        controller = newController;
        whitelist[newController] = true;
    }
    
    /**
     * @dev Pause all token transfers
     */
    function pause() external onlyOwner {
        _pause();
    }
    
    /**
     * @dev Unpause all token transfers
     */
    function unpause() external onlyOwner {
        _unpause();
    }
    
    /**
     * @dev Controller forced transfer
     * @param from Token holder
     * @param to Token recipient
     * @param value Amount of tokens
     * @param data Additional data
     * @param operatorData Additional operator data
     */
    function controllerTransfer(
        address from,
        address to,
        uint256 value,
        bytes calldata data,
        bytes calldata operatorData
    ) external onlyController {
        _controllerTransfer(from, to, value, data, operatorData);
    }
    
    /**
     * @dev Controller forced redemption
     * @param tokenHolder Token holder
     * @param value Amount of tokens
     * @param data Additional data
     * @param operatorData Additional operator data
     */
    function controllerRedeem(
        address tokenHolder,
        uint256 value,
        bytes calldata data,
        bytes calldata operatorData
    ) external onlyController {
        _controllerRedeem(tokenHolder, value, data, operatorData);
    }
    
    /**
     * @dev EIP-712 typed data hash for gasless minting
     */
    function DOMAIN_SEPARATOR() external view returns (bytes32) {
        return _domainSeparatorV4();
    }
    
    /**
     * @dev EIP-712 typed data hash for minting
     */
    function MINT_TYPEHASH() public pure returns (bytes32) {
        return keccak256("Mint(address to,uint256 value,bytes32 partition,uint256 nonce,uint256 deadline)");
    }
    
    /**
     * @dev Mint tokens with EIP-712 signature (gasless)
     * @param to Token recipient
     * @param value Amount of tokens
     * @param partition Token partition
     * @param deadline Signature deadline
     * @param v Signature v
     * @param r Signature r
     * @param s Signature s
     */
    function mintWithSignature(
        address to,
        uint256 value,
        bytes32 partition,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external {
        require(block.timestamp <= deadline, "PropPulseToken: expired deadline");
        
        // Get the nonce for the recipient
        uint256 nonce = _useNonce(to);
        
        // Verify signature
        bytes32 structHash = keccak256(
            abi.encode(
                MINT_TYPEHASH(),
                to,
                value,
                partition,
                nonce,
                deadline
            )
        );
        bytes32 hash = _hashTypedDataV4(structHash);
        address signer = ECDSA.recover(hash, v, r, s);
        
        require(signer == owner() || signer == controller, "PropPulseToken: invalid signature");
        
        // Mint tokens
        _issueByPartition(partition, to, value, "");
    }
    
    /**
     * @dev Hook that is called before any transfer of tokens
     */
    function _beforeTokenTransfer(
        address operator,
        address from,
        address to,
        uint256 amount
    ) internal override whenNotPaused {
        super._beforeTokenTransfer(operator, from, to, amount);
        
        // Skip whitelist check for minting and burning
        if (from != address(0) && to != address(0)) {
            require(whitelist[from] && whitelist[to], "PropPulseToken: transfer to/from non-whitelisted address");
        }
    }
    
    /**
     * @dev Internal function to execute controller transfer
     */
    function _controllerTransfer(
        address from,
        address to,
        uint256 value,
        bytes memory data,
        bytes memory operatorData
    ) internal {
        require(to != address(0), "PropPulseToken: transfer to the zero address");
        
        // Get default partitions
        bytes32[] memory partitions = _getDefaultPartitions();
        require(partitions.length > 0, "PropPulseToken: no default partition");
        
        // Transfer tokens from the default partition
        _operatorTransferByPartition(
            partitions[0],
            msg.sender,
            from,
            to,
            value,
            data,
            operatorData
        );
        
        emit ControllerTransfer(msg.sender, from, to, value, data, operatorData);
    }
    
    /**
     * @dev Internal function to execute controller redemption
     */
    function _controllerRedeem(
        address tokenHolder,
        uint256 value,
        bytes memory data,
        bytes memory operatorData
    ) internal {
        require(tokenHolder != address(0), "PropPulseToken: redeem from the zero address");
        
        // Get default partitions
        bytes32[] memory partitions = _getDefaultPartitions();
        require(partitions.length > 0, "PropPulseToken: no default partition");
        
        // Redeem tokens from the default partition
        _operatorRedeemByPartition(
            partitions[0],
            msg.sender,
            tokenHolder,
            value,
            data,
            operatorData
        );
        
        emit ControllerRedemption(msg.sender, tokenHolder, value, data, operatorData);
    }
    
    /**
     * @dev Function that should revert when `msg.sender` is not authorized to upgrade the contract
     */
    function _authorizeUpgrade(address newImplementation) internal override onlyOwner {}
    
    /**
     * @dev Returns the current nonce for an address and increments it
     */
    function _useNonce(address owner) internal returns (uint256 current) {
        // Use the nonce from EIP712Upgradeable
        current = _useNonce(owner);
    }
}
