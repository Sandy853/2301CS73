// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "../src/Escrow.sol";

interface Vm {
    function prank(address) external;
    function deal(address, uint256) external;
    function expectRevert() external;
    function expectEmit(bool, bool, bool, bool) external;
}

contract EscrowTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address constant B = address(0xB001);
    address constant S = address(0x5001);
    address constant A = address(0xA001);
    address constant X = address(0xDEAD);
    uint256 constant PRICE = 1 ether;
    Escrow e;

    event Funded(address indexed buyer, uint256 amount);
    event Released(address indexed seller, uint256 amount);
    event Disputed(address indexed by);
    event DisputeResolved(address indexed recipient, uint256 amount);
    event Withdrawal(address indexed recipient, uint256 amount);

    function setUp() public { e = new Escrow(B,S,A,PRICE); vm.deal(B,100 ether); }
    function assertEq(uint256 a,uint256 b) internal pure { require(a==b,"not equal"); }
    function assertState(Escrow.State s) internal view { require(e.state()==s,"wrong state"); }
    function invariantAccounting() internal view { assertEq(address(e).balance,e.liabilities()); }
    function fundIt() internal { vm.prank(B); e.fund{value:PRICE}(); invariantAccounting(); }
    function testCreatedCancellation() public {
        vm.prank(B); e.approveCancellation(); assertState(Escrow.State.Created);
        vm.prank(S); e.approveCancellation(); assertState(Escrow.State.Cancelled);
        invariantAccounting();
        vm.expectRevert(); vm.prank(B); e.fund{value:PRICE}();
        vm.expectRevert(); vm.prank(S); e.approveCancellation();
        vm.expectRevert(); vm.prank(B); e.release();
        vm.expectRevert(); vm.prank(B); e.dispute();
        vm.expectRevert(); vm.prank(A); e.resolve(true);
    }
    function testSellerFirstCancellation() public {
        vm.prank(S); e.approveCancellation(); vm.prank(B); e.approveCancellation();
        assertState(Escrow.State.Cancelled); invariantAccounting();
    }
    function testFundingReleaseWithdrawAndEvents() public {
        vm.expectEmit(true,false,false,true); emit Funded(B,PRICE);
        fundIt(); assertState(Escrow.State.Funded);
        vm.expectEmit(true,false,false,true); emit Released(S,PRICE);
        vm.prank(B); e.release(); assertState(Escrow.State.Released); invariantAccounting();
        assertEq(e.pending(S),PRICE);
        vm.expectEmit(true,false,false,true); emit Withdrawal(S,PRICE);
        uint256 beforeBal = S.balance; vm.prank(S); e.withdraw();
        assertEq(S.balance-beforeBal,PRICE); invariantAccounting();
        vm.expectRevert(); vm.prank(S); e.withdraw();
        assertTerminal();
    }
    function testDisputeBuyerWins() public {
        fundIt(); vm.expectEmit(true,false,false,true); emit Disputed(S);
        vm.prank(S); e.dispute(); assertState(Escrow.State.Disputed);
        vm.expectEmit(true,false,false,true); emit DisputeResolved(B,PRICE);
        vm.prank(A); e.resolve(false); assertState(Escrow.State.ResolvedToBuyer);
        invariantAccounting(); vm.prank(B); e.withdraw(); invariantAccounting(); assertTerminal();
    }
    function testDisputeSellerWins() public {
        fundIt(); vm.expectEmit(true,false,false,true); emit Disputed(B);
        vm.prank(B); e.dispute();
        vm.expectEmit(true,false,false,true); emit DisputeResolved(S,PRICE);
        vm.prank(A); e.resolve(true); assertState(Escrow.State.ResolvedToSeller);
        invariantAccounting(); vm.prank(S); e.withdraw(); invariantAccounting(); assertTerminal();
    }
    function assertTerminal() internal {
        vm.expectRevert(); vm.prank(B); e.release();
        vm.expectRevert(); vm.prank(B); e.dispute();
        vm.expectRevert(); vm.prank(A); e.resolve(false);
        vm.expectRevert(); vm.prank(B); e.fund{value:PRICE}();
        vm.expectRevert(); vm.prank(S); e.approveCancellation();
    }
    function testRejectEveryInvalidTransitionAndRole() public {
        vm.expectRevert(); vm.prank(X); e.fund{value:PRICE}();
        vm.expectRevert(); vm.prank(B); e.fund{value:PRICE-1}();
        vm.expectRevert(); vm.prank(X); e.approveCancellation();
        vm.expectRevert(); vm.prank(B); e.release();
        vm.expectRevert(); vm.prank(S); e.dispute();
        vm.expectRevert(); vm.prank(A); e.resolve(true);
        vm.prank(B); e.approveCancellation();
        vm.expectRevert(); vm.prank(B); e.approveCancellation();
        fundIt();
        vm.expectRevert(); vm.prank(B); e.fund{value:PRICE}();
        vm.expectRevert(); vm.prank(B); e.approveCancellation();
        vm.expectRevert(); vm.prank(S); e.release();
        vm.expectRevert(); vm.prank(X); e.release();
        vm.expectRevert(); vm.prank(A); e.resolve(true);
        vm.expectRevert(); vm.prank(X); e.dispute();
        vm.prank(S); e.dispute();
        vm.expectRevert(); vm.prank(B); e.release();
        vm.expectRevert(); vm.prank(B); e.dispute();
        vm.expectRevert(); vm.prank(X); e.resolve(true);
        vm.expectRevert(); vm.prank(B); e.resolve(true);
        vm.prank(A); e.resolve(true); assertTerminal(); invariantAccounting();
    }
    function testRejectBadConstructor() public {
        vm.expectRevert(); new Escrow(address(0),S,A,PRICE);
        vm.expectRevert(); new Escrow(B,address(0),A,PRICE);
        vm.expectRevert(); new Escrow(B,S,address(0),PRICE);
        vm.expectRevert(); new Escrow(B,B,A,PRICE);
        vm.expectRevert(); new Escrow(B,S,B,PRICE);
        vm.expectRevert(); new Escrow(B,S,S,PRICE);
        vm.expectRevert(); new Escrow(B,S,A,0);
    }
    function testFuzzDepositAmount(uint96 raw) public {
        uint256 amount = uint256(raw) + 1;
        Escrow x = new Escrow(B,S,A,amount);
        vm.deal(B,amount); vm.prank(B); x.fund{value:amount}();
        assertEq(x.liabilities(),amount); assertEq(address(x).balance,amount);
        vm.prank(B); x.release(); assertEq(x.pending(S),amount);
        assertEq(x.liabilities(),amount); vm.prank(S); x.withdraw();
        assertEq(x.liabilities(),0); assertEq(address(x).balance,0);
    }
    function testFuzzCallerRoles(uint8 role) public {
        address who = role % 4 == 0 ? B : role % 4 == 1 ? S : role % 4 == 2 ? A : X;
        if (who != B) { vm.expectRevert(); vm.prank(who); e.fund{value:PRICE}(); }
        else { vm.prank(who); e.fund{value:PRICE}(); }
        invariantAccounting();
    }
    function testFuzzResolutionRole(uint8 role,bool paySeller) public {
        fundIt(); vm.prank(B); e.dispute();
        address who = role % 4 == 0 ? B : role % 4 == 1 ? S : role % 4 == 2 ? A : X;
        if (who != A) { vm.expectRevert(); vm.prank(who); e.resolve(paySeller); }
        else { vm.prank(who); e.resolve(paySeller); }
        invariantAccounting();
    }
}
