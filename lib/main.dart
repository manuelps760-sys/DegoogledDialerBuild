import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() => runApp(const DegoogledDialerApp());

class DegoogledDialerApp extends StatelessWidget {
  const DegoogledDialerApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Degoogled Dialer',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff3568d4), brightness: Brightness.dark), useMaterial3: true),
    home: const DialerHome(),
  );
}

class DialerHome extends StatefulWidget {
  const DialerHome({super.key});
  @override
  State<DialerHome> createState() => _DialerHomeState();
}

class _DialerHomeState extends State<DialerHome> {
  static const platform = MethodChannel('org.degoogled.dialer/phone');
  final number = TextEditingController();
  final sipUser = TextEditingController();
  final sipServer = TextEditingController();
  int tab = 0;
  String status = 'Ready. Calling has not yet been device-tested.';
  String sipStatus = 'SIP engine is not implemented in this MVP.';
  bool defaultDialer = false;

  @override
  void initState() { super.initState(); _refreshRole(); }
  Future<void> _refreshRole() async {
    try {
      final held = await platform.invokeMethod<bool>('isDefaultDialer') ?? false;
      if (mounted) setState(() => defaultDialer = held);
    } on PlatformException catch (e) { if (mounted) setState(() => status = 'Phone integration: ${e.message ?? e.code}'); }
  }
  Future<void> _chooseDefault() async {
    try {
      final result = await platform.invokeMethod<bool>('requestDefaultDialer');
      await _refreshRole();
      if (mounted) setState(() => status = result == true ? 'Default phone role granted.' : 'Complete or cancel Android’s default-phone prompt, then refresh.');
    } on PlatformException catch (e) { setState(() => status = 'Could not request dialer role: ${e.message ?? e.code}'); }
  }
  Future<void> _call() async {
    final value = number.text.trim();
    if (value.isEmpty) { setState(() => status = 'Enter a phone number first.'); return; }
    try {
      await platform.invokeMethod('placeCall', {'number': value});
      setState(() => status = defaultDialer ? 'Call request sent to Android Telecom. Verify on-device.' : 'Opened Android dialer; tap call there.');
    } on PlatformException catch (e) { setState(() => status = 'Call request failed: ${e.message ?? e.code}'); }
  }
  void _key(String key) { number.text += key; number.selection = TextSelection.collapsed(offset: number.text.length); }
  Widget _dialPad() {
    const keys = ['1','2','3','4','5','6','7','8','9','*','0','#'];
    return Column(children: [
      TextField(controller: number, keyboardType: TextInputType.phone, textAlign: TextAlign.center, style: const TextStyle(fontSize: 28), decoration: const InputDecoration(hintText: 'Enter number', border: OutlineInputBorder())),
      const SizedBox(height: 18),
      GridView.count(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), crossAxisCount: 3, childAspectRatio: 1.7, children: keys.map((k) => Padding(padding: const EdgeInsets.all(4), child: FilledButton.tonal(onPressed: () => _key(k), child: Text(k, style: const TextStyle(fontSize: 24))))).toList()),
      const SizedBox(height: 12),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        IconButton(onPressed: () { if (number.text.isNotEmpty) number.text = number.text.substring(0, number.text.length - 1); }, icon: const Icon(Icons.backspace_outlined)),
        const SizedBox(width: 18),
        FilledButton.icon(onPressed: _call, icon: const Icon(Icons.call), label: const Text('Call')),
        const SizedBox(width: 18),
        IconButton(onPressed: () => setState(() => number.clear()), icon: const Icon(Icons.clear)),
      ]),
      const SizedBox(height: 8),
      Text(status, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
    ]);
  }
  Widget _phoneSettings() => ListView(padding: const EdgeInsets.all(18), children: [
    const Icon(Icons.phone_android, size: 48),
    const SizedBox(height: 10),
    Text('Android calling integration', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 8),
    ListTile(leading: Icon(defaultDialer ? Icons.verified : Icons.info_outline), title: Text(defaultDialer ? 'Default phone app selected' : 'Default phone app not selected'), subtitle: const Text('Android controls the SIM, carrier, emergency-call, and Telecom permissions.')),
    FilledButton(onPressed: _chooseDefault, child: const Text('Choose as default phone app')),
    OutlinedButton(onPressed: _refreshRole, child: const Text('Refresh role status')),
    const SizedBox(height: 12),
    const Text('Incoming-call answer/reject controls are registered through a native InCallService. Their behavior still needs testing on this phone.'),
  ]);
  Widget _sipPage() => ListView(padding: const EdgeInsets.all(18), children: [
    const Icon(Icons.public, size: 48),
    const SizedBox(height: 10),
    Text('SIP / VoIP', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 8),
    const Text('The SIP interface is scaffolded, but registration, SIP signaling, negotiated media, and two-way audio are not implemented in this Flutter MVP. No registration or call will be simulated.'),
    const SizedBox(height: 16),
    TextField(controller: sipUser, decoration: const InputDecoration(labelText: 'SIP username', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    TextField(controller: sipServer, decoration: const InputDecoration(labelText: 'SIP server / domain', border: OutlineInputBorder())),
    const SizedBox(height: 12),
    FilledButton.icon(onPressed: () => setState(() => sipStatus = 'Not connected: SIP engine is not implemented. Credentials have not been sent or stored.'), icon: const Icon(Icons.info_outline), label: const Text('Check SIP readiness')),
    const SizedBox(height: 12),
    Text(sipStatus),
    const SizedBox(height: 16),
    const Text('Next SIP milestone: integrate a maintained native SIP/media stack, then test codec negotiation, NAT traversal, and both audio directions.'),
  ]);
  @override
  void dispose() { number.dispose(); sipUser.dispose(); sipServer.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Degoogled Dialer'), actions: [IconButton(tooltip: 'Default dialer', onPressed: _chooseDefault, icon: const Icon(Icons.phone_android))]),
    body: SafeArea(child: IndexedStack(index: tab, children: [
      SingleChildScrollView(padding: const EdgeInsets.all(18), child: _dialPad()),
      _phoneSettings(),
      _sipPage(),
    ])),
    bottomNavigationBar: NavigationBar(selectedIndex: tab, onDestinationSelected: (i) => setState(() => tab = i), destinations: const [
      NavigationDestination(icon: Icon(Icons.dialpad), label: 'Dial pad'),
      NavigationDestination(icon: Icon(Icons.settings_phone), label: 'Phone'),
      NavigationDestination(icon: Icon(Icons.public), label: 'SIP / VoIP'),
    ]),
  );
}
