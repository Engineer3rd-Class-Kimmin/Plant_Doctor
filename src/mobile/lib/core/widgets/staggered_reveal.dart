import 'dart:async';

import 'package:flutter/material.dart';

import '../navigation/app_route_observer.dart';

class StaggeredReveal extends StatefulWidget {
  const StaggeredReveal({
    super.key,
    required this.index,
    required this.child,
    this.stepDelay = const Duration(milliseconds: 110),
    this.duration = const Duration(milliseconds: 300),
    this.offset = const Offset(0, 0.06),
  });

  final int index;
  final Widget child;
  final Duration stepDelay;
  final Duration duration;
  final Offset offset;

  @override
  State<StaggeredReveal> createState() => _StaggeredRevealState();
}

class _StaggeredRevealState extends State<StaggeredReveal>
    with RouteAware {
  Timer? _timer;
  bool _visible = false;
  ModalRoute<void>? _route;

  @override
  void initState() {
    super.initState();
    _schedule();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    final route = ModalRoute.of(context);

    if (_route != route) {
      if (_route != null) {
        appRouteObserver.unsubscribe(this);
      }

      _route = route;

      if (route != null) {
        appRouteObserver.subscribe(this, route);
      }
    }
  }

  @override
  void didUpdateWidget(covariant StaggeredReveal oldWidget) {
    super.didUpdateWidget(oldWidget);

    if (oldWidget.index != widget.index) {
      _restartAnimation();
    }
  }

  @override
  void didPopNext() {
    _restartAnimation();
  }

  void _restartAnimation() {
    _timer?.cancel();

    if (mounted) {
      setState(() {
        _visible = false;
      });
    }

    _schedule();
  }

  void _schedule() {
    final delay = Duration(
      milliseconds: widget.stepDelay.inMilliseconds * widget.index,
    );

    _timer = Timer(delay, () {
      if (!mounted) return;

      setState(() {
        _visible = true;
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    appRouteObserver.unsubscribe(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      opacity: _visible ? 1 : 0,
      duration: widget.duration,
      curve: Curves.easeOutQuart,
      child: AnimatedSlide(
        offset: _visible ? Offset.zero : widget.offset,
        duration: widget.duration,
        curve: Curves.easeOutQuart,
        child: widget.child,
      ),
    );
  }
}