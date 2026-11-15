// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice One-shot, fixed-price escrow. All three roles must be distinct.
contract Escrow {
    enum State { Created, Funded, Cancelled, Released, Disputed, ResolvedToBuyer, ResolvedToSeller }
    error ZeroAddress();
    error DuplicateRole();
    error Unauthorized();
    error InvalidState(State actual);
    error InvalidAmount(uint256 supplied);
    error AlreadyApproved();
    error NothingToWithdraw();
    error ReentrantCall();
    error TransferFailed();

    event Funded(address indexed buyer, uint256 amount);
    event CancellationApproved(address indexed approver);
    event Cancelled();
    event Released(address indexed seller, uint256 amount);
    event Disputed(address indexed by);
    event DisputeResolved(address indexed recipient, uint256 amount);
    event Withdrawal(address indexed recipient, uint256 amount);

    address public immutable buyer;
    address public immutable seller;
    address public immutable arbiter;
    uint256 public immutable price;
    State public state;
    bool public buyerApprovedCancel;
    bool public sellerApprovedCancel;
    uint256 public escrowed;
    uint256 public totalPending;
    mapping(address => uint256) public pending;
    uint256 private locked = 1;

    modifier onlyBuyer() { if (msg.sender != buyer) revert Unauthorized(); _; }
    modifier onlyParty() { if (msg.sender != buyer && msg.sender != seller) revert Unauthorized(); _; }
    modifier onlyArbiter() { if (msg.sender != arbiter) revert Unauthorized(); _; }
    modifier atState(State expected) { if (state != expected) revert InvalidState(state); _; }
    modifier nonReentrant() {
        if (locked != 1) revert ReentrantCall();
        locked = 2;
        _;
        locked = 1;
    }

    constructor(address buyer_, address seller_, address arbiter_, uint256 price_) {
        if (buyer_ == address(0) || seller_ == address(0) || arbiter_ == address(0)) revert ZeroAddress();
        if (buyer_ == seller_ || buyer_ == arbiter_ || seller_ == arbiter_) revert DuplicateRole();
        if (price_ == 0) revert InvalidAmount(price_);
        buyer = buyer_; seller = seller_; arbiter = arbiter_; price = price_;
    }

    function fund() external payable onlyBuyer atState(State.Created) {
        if (msg.value != price) revert InvalidAmount(msg.value);
        escrowed = msg.value;
        state = State.Funded;
        emit Funded(msg.sender, msg.value);
    }

    /// @notice Cancellation is available ONLY in Created, before any deposit.
    function approveCancellation() external onlyParty atState(State.Created) {
        if (msg.sender == buyer) {
            if (buyerApprovedCancel) revert AlreadyApproved();
            buyerApprovedCancel = true;
        } else {
            if (sellerApprovedCancel) revert AlreadyApproved();
            sellerApprovedCancel = true;
        }
        emit CancellationApproved(msg.sender);
        if (buyerApprovedCancel && sellerApprovedCancel) {
            state = State.Cancelled;
            emit Cancelled();
        }
    }

    function release() external onlyBuyer atState(State.Funded) {
        uint256 amount = escrowed;
        escrowed = 0;
        state = State.Released;
        pending[seller] += amount;
        totalPending += amount;
        emit Released(seller, amount);
    }

    function dispute() external onlyParty atState(State.Funded) {
        state = State.Disputed;
        emit Disputed(msg.sender);
    }

    function resolve(bool paySeller) external onlyArbiter atState(State.Disputed) {
        address recipient = paySeller ? seller : buyer;
        uint256 amount = escrowed;
        escrowed = 0;
        state = paySeller ? State.ResolvedToSeller : State.ResolvedToBuyer;
        pending[recipient] += amount;
        totalPending += amount;
        emit DisputeResolved(recipient, amount);
    }

    /// @notice Withdrawal changes accounting but never changes a terminal state.
    function withdraw() external nonReentrant {
        uint256 amount = pending[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        pending[msg.sender] = 0;
        totalPending -= amount;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Withdrawal(msg.sender, amount);
    }

    function liabilities() external view returns (uint256) { return escrowed + totalPending; }

    // Forced ETH (e.g. selfdestruct) is outside normal escrow accounting.
    receive() external payable { revert InvalidAmount(msg.value); }
    fallback() external payable { revert InvalidAmount(msg.value); }
}
